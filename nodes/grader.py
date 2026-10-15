import os
import re
import json
from utils.llm_client import LLMClient
from utils.injection_detector import detect_injection
from utils.content_safety import check_content_safety
from utils.privacy import anonymize_text
from utils.similarity import SimilarityChecker
from knowledge_base.chroma_store import KnowledgeBase
from nodes import verifier
from nodes.rubric_io import compute_subtotals, LEVELS

GRADING_PROMPT = """You are an expert experiment report grader. Grade the report ONLY on the criteria listed below, strictly according to their level descriptors.

## 评分维度（只评这些）
{criteria_block}

## Student Report (Text)
{report_text}

## Student Report (Image Descriptions)
{image_descriptions}

{knowledge_context}

## Requirements
1. For EACH criterion above, assign a level (A/B/C/D) and provide SPECIFIC evidence quoted from the report
2. Each piece of evidence must reference the actual content of the report
3. Be consistent: same quality of work = same score regardless of writing style
4. Output a JSON object in this exact format:
{{
  "scores": {{
    "criterion_name": {{
      "level": "A/B/C/D",
      "evidence": "quote from report that justifies this level",
      "reasoning": "brief explanation of why this evidence maps to this level"
    }}
  }},
  "summary": "2-3 sentence overall assessment",
  "flags": []
}}"""


def _parse_json(text):
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_response": text, "scores": {}}


def _coerce_rubric(rubric):
    if isinstance(rubric, dict):
        return rubric
    criteria = []
    for line in rubric.splitlines():
        m = re.match(r"\|\s*([^|]+?)\s*\|\s*([\d.]+)\s*%\s*\|", line)
        if m and m.group(1).strip() not in ("维度",):
            cells = [c.strip() for c in line.split("|")]
            criteria.append({
                "name": m.group(1).strip(), "weight": float(m.group(2)), "mechanical": False,
                "doc_ref": cells[4] if len(cells) > 4 else "",
                "levels": {"A": cells[5] if len(cells) > 5 else "", "B": cells[6] if len(cells) > 6 else "",
                           "C": cells[7] if len(cells) > 7 else "", "D": cells[8] if len(cells) > 8 else ""},
                "user_edited": [], "rules": None,
            })
    return {"criteria": criteria}


class Grader:
    def __init__(self, rubric, llm_client=None, config=None, output_dir=None, similarity_scope=None):
        self.rubric = _coerce_rubric(rubric)
        self.llm = llm_client or LLMClient()
        self.config = config or {}
        self.batch_size = self.config.get("grading", {}).get("batch_size", 5)
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), "..", "output", "grading")
        os.makedirs(self.output_dir, exist_ok=True)
        self.results = []
        self.pending_review = []
        self.kb = KnowledgeBase()
        self.similarity = SimilarityChecker(self.kb.client,
                                            collection_name=f"report_similarity_{similarity_scope or 'default'}")

    def _criteria_block(self, criteria):
        blocks = []
        for c in criteria:
            lv = c.get("levels", {})
            blocks.append(
                f"### {c['name']}（权重 {c.get('weight')}%，标准文档位置：{c.get('doc_ref', '未标注')}）\n"
                f"- A: {lv.get('A', '')}\n- B: {lv.get('B', '')}\n- C: {lv.get('C', '')}\n- D: {lv.get('D', '')}"
            )
        return "\n\n".join(blocks)

    def _verify_mechanical(self, text):
        scores, fallback = {}, []
        for c in self.rubric.get("criteria", []):
            if not c.get("mechanical"):
                continue
            v = verifier.verify(text, c.get("rules"))
            if v["verdict"] == "ok":
                scores[c["name"]] = {
                    "level": "A" if v["passed"] else "D",
                    "evidence": v["detail"],
                    "reasoning": "程序化判决（verifier.py）",
                    "mechanical": True,
                }
            else:
                fallback.append(c)
        return scores, fallback

    def assign_images(self, image_entries):
        if not image_entries:
            return {}
        criteria_names = [c["name"] for c in self.rubric.get("criteria", [])]
        items = [{"id": e["id"], "ocr_text": e.get("text", "")[:300]} for e in image_entries]
        prompt = (
            "把每张图片归入最相关的评分维度。评分维度："
            + "、".join(criteria_names)
            + "\n图片列表（JSON）："
            + json.dumps(items, ensure_ascii=False)
            + '\n输出 JSON：{"assignments": [{"id": "...", "criterion": "...", "reason": "..."}]}，'
            + "无法判断的 criterion 填 null。只输出 JSON。"
        )
        data = _parse_json(self.llm.chat([{"role": "user", "content": prompt}], temperature=0.1))
        valid = set(criteria_names)
        return {a.get("id"): {"criterion": a.get("criterion"), "reason": a.get("reason", "")}
                for a in data.get("assignments", []) if a.get("criterion") in valid}

    def grade_single(self, report_id, text, image_descriptions=None):
        injection_result = detect_injection(text)
        if injection_result["is_injection"]:
            result = {"report_id": report_id, "status": "flagged_injection",
                      "injection_details": injection_result}
            self.results.append(result)
            return {"result": result, "needs_review": False}

        safety_result = check_content_safety(text)
        if safety_result["verdict"] == "blocked":
            result = {"report_id": report_id, "status": "blocked_safety",
                      "safety_details": safety_result}
            self.results.append(result)
            return {"result": result, "needs_review": False}

        similarity_warnings = self.similarity.check_against_all(report_id, text)
        self.similarity.add_report(report_id, text)

        similar_cases = self.kb.search_similar(text, n_results=3)
        knowledge_context = ""
        if similar_cases:
            cases_text = []
            for case in similar_cases:
                grading = case["metadata"].get("grading_json", "")
                cases_text.append(f"Reference case (similarity: {1 - case['distance']:.2f}):\n{case['document'][:500]}\nPrevious grading: {grading}")
            knowledge_context = "## Similar Reference Cases\n" + "\n---\n".join(cases_text)

        scores, fallback = self._verify_mechanical(text)
        semantic = [c for c in self.rubric.get("criteria", []) if c["name"] not in scores]
        semantic += fallback
        img_desc = image_descriptions or "No images in this report."
        prompt = GRADING_PROMPT.format(
            criteria_block=self._criteria_block(semantic),
            report_text=text[:8000],
            image_descriptions=img_desc,
            knowledge_context=knowledge_context,
        )
        llm_response = self.llm.chat([{"role": "user", "content": prompt}], temperature=0.1)
        grading = _parse_json(llm_response)
        for name, entry in scores.items():
            grading.setdefault("scores", {}).setdefault(name, entry)
        for c in semantic:
            name = c["name"]
            entry = grading.setdefault("scores", {}).get(name)
            if not isinstance(entry, dict) or entry.get("level") not in LEVELS:
                grading["scores"][name] = {
                    "level": "C", "evidence": "", "reasoning": "LLM 未返回该维度，默认 C，请人工复核"}
        ordered = {c["name"]: grading["scores"][c["name"]] for c in self.rubric.get("criteria", [])
                   if c["name"] in grading.get("scores", {})}
        for name, entry in grading.get("scores", {}).items():
            ordered.setdefault(name, entry)
        grading["scores"] = ordered
        grading["subtotals"] = compute_subtotals(ordered, self.rubric)
        grading.pop("total_weighted_score", None)

        result = {
            "report_id": report_id,
            "status": "graded",
            "grading": grading,
            "similarity_warnings": similarity_warnings,
            "safety_warnings": safety_result.get("warned", []),
        }
        self.results.append(result)
        self.pending_review.append(result)

        if len(self.pending_review) >= self.batch_size:
            return {"result": result, "needs_review": True, "batch": list(self.pending_review)}
        return {"result": result, "needs_review": False}

    def approve_batch(self):
        approved = []
        for r in self.pending_review:
            if r["status"] == "graded":
                anonymized, _ = anonymize_text(r.get("_report_text", ""))
                scrubbed_json, _ = anonymize_text(json.dumps(r["grading"], ensure_ascii=False))
                try:
                    scrubbed_grading = json.loads(scrubbed_json)
                except json.JSONDecodeError:
                    scrubbed_grading = r["grading"]
                self.kb.add_case(f"case_{r['report_id']}", anonymized, scrubbed_grading)
                approved.append(r)
        self.pending_review = []
        return approved

    def reject_batch(self, corrections):
        rejected = list(self.pending_review)
        self.pending_review = []
        return {"rejected": rejected, "corrections": corrections}

    def export_results(self, filepath=None):
        if filepath is None:
            filepath = os.path.join(self.output_dir, "grading_results.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        return filepath

    def export_excel(self, filepath=None):
        if filepath is None:
            filepath = os.path.join(self.output_dir, "grading_summary.xlsx")
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "评分汇总"
        ws.append(["报告ID", "状态", "程序化小计", "语义小计", "总分", "各维度评分"])
        for r in self.results:
            row = [r["report_id"], r["status"]]
            if r["status"] == "graded" and "grading" in r:
                st = r["grading"].get("subtotals", {})
                row += [st.get("procedural", ""), st.get("semantic", ""), st.get("total", "")]
                scores = r["grading"].get("scores", {})
                row.append("; ".join(f"{k}: {v.get('level', 'N/A')}" for k, v in scores.items()))
            else:
                row += ["", "", "", "N/A"]
            ws.append(row)
        wb.save(filepath)
        return filepath
