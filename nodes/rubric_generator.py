import os
import re
import json
from utils.llm_client import LLMClient

RUBRIC_GENERATION_PROMPT = """You are an expert in assessment design and rubric construction.
Generate a criterion-referenced rubric in Markdown table format for grading experiment reports.

## Input: Extracted grading criteria from teacher's document
{criteria_text}

## Requirements
1. Extract all grading dimensions/criteria from the input. Be comprehensive — include as many distinct criteria as possible (e.g., experiment purpose, theoretical basis, procedure design, data recording, data analysis, error analysis, conclusion, format/structure, originality, safety awareness, etc.)
2. Use exactly 4 performance levels per criterion: A (exemplary), B (proficient), C (developing), D (beginning)
3. Use DESCRIPTIVE language, not evaluative:
   - NEVER use: excellent, good, satisfactory, poor, limited, basic, outstanding, weak
   - INSTEAD: describe specifically what is PRESENT in the work at each level
   - Bad: "Good data analysis" → Good: "Data analysis includes calculation of mean, standard deviation, and identifies at least two sources of systematic error with quantitative impact estimates"
4. Adjacent levels must be qualitatively distinct — not just "more" or "less" of the same thing
5. Each criterion must be independently scorable
6. Output MUST be in this exact Markdown format:

# 实验报告评分细则 (Rubric)

## 评分维度

| 维度 | 权重 | A (优秀) | B (良好) | C (及格) | D (不及格) |
|------|------|----------|----------|----------|------------|
| {{criterion_name}} | {{weight}}% | {{descriptor}} | {{descriptor}} | {{descriptor}} | {{descriptor}} |
| ... | ... | ... | ... | ... | ... |

## 评分说明
{{brief explanation of how to use this rubric}}

## 校准笔记
{{notes on borderline cases and key decision points between levels}}

Generate the rubric now. Write ALL descriptors in Chinese."""

CALIBRATION_PROMPT = """You are an assessment calibration expert. A teacher has manually graded a student's experiment report using a rubric, and you also graded it independently. Compare and analyze the differences.

## Rubric
{rubric}

## Student Report
{report_text}

## Teacher's Grading
{teacher_grading}

## AI's Grading
{ai_grading}

## Task
1. For each criterion where the scores differ, explain WHY the difference occurred
2. Suggest specific adjustments to the rubric descriptors to make boundaries clearer
3. Output a JSON object:
{{
  "agreements": ["list of criteria where scores matched"],
  "disagreements": [
    {{
      "criterion": "...",
      "teacher_score": "...",
      "ai_score": "...",
      "reason": "why they differ",
      "suggested_rubric_adjustment": "how to clarify the rubric"
    }}
  ],
  "suggested_rubric_revisions": "full revised rubric markdown if changes needed, or null"
}}"""

ITERATION_PROMPT = """You are an assessment calibration expert (TALEC-style shot iteration).
The judge LLM graded some cases with the current rubric; human judgments exist for the same cases and are the ground truth.
Analyze the mismatches and propose a revised rubric.

## 原始规范（唯一事实来源，不得新增其中不存在的条款）
{spec}

## 当前判定细则
{rubric}

## 不匹配案例（人工判定为准）
{mismatches}

## 任务
1. 逐案分析不一致原因：细则描述模糊 / 条款优先级缺失 / LLM 数值误读 / 案例标注歧义
2. 修订判定细则：只依据原始规范；条款边界必须定量、可核对（描述性语言，不用评价词）；补充条款优先级与互斥关系；在"校准笔记"中写清边界案例的判定方法

## 输出格式（严格遵守，不要使用代码围栏）
###分析
{{"mismatch_reasons": [{{"case_id": "...", "reason": "..."}}], "possible_causes": ["..."]}}
###修订细则
（完整修订后的 Markdown 细则，原生输出）"""


def _extract_json(text):
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


class RubricGenerator:
    def __init__(self, llm_client=None, output_dir=None):
        self.llm = llm_client or LLMClient()
        self.output_dir = output_dir or os.path.join(os.path.dirname(__file__), "..", "output", "rubrics")
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_from_file(self, criteria_file_path):
        ext = os.path.splitext(criteria_file_path)[1].lower()
        if ext == ".pdf":
            import pymupdf
            doc = pymupdf.open(criteria_file_path)
            text = "\n".join(page.get_text("text") for page in doc)
            doc.close()
        elif ext == ".docx":
            from docx import Document
            doc = Document(criteria_file_path)
            text = "\n".join(p.text for p in doc.paragraphs)
        else:
            with open(criteria_file_path, "r", encoding="utf-8") as f:
                text = f.read()
        return self.generate_from_text(text)

    def generate_from_text(self, criteria_text):
        prompt = RUBRIC_GENERATION_PROMPT.format(criteria_text=criteria_text)
        messages = [{"role": "user", "content": prompt}]
        rubric_md = self.llm.chat(messages)
        self._save_rubric(rubric_md, "rubric_latest.md")
        return rubric_md

    def iterate(self, spec, rubric, mismatches):
        prompt = ITERATION_PROMPT.format(
            spec=spec,
            rubric=rubric,
            mismatches=json.dumps(mismatches, ensure_ascii=False, indent=2),
        )
        messages = [{"role": "user", "content": prompt}]
        result_text = self.llm.chat(messages, temperature=0.2)
        parts = re.split(r"###\s*修订细则", result_text, maxsplit=1)
        analysis = _extract_json(parts[0].split("###分析")[-1])
        analysis.setdefault("mismatch_reasons", [])
        analysis.setdefault("possible_causes", [])
        if len(parts) > 1:
            revised = parts[1].strip()
            if revised:
                analysis["revised_rubric"] = revised
        else:
            analysis.setdefault("possible_causes", analysis.get("possible_causes") or ["LLM 未按格式输出修订细则"])
        return analysis

    def calibrate(self, rubric, report_text, teacher_grading, ai_grading):
        prompt = CALIBRATION_PROMPT.format(
            rubric=rubric,
            report_text=report_text,
            teacher_grading=json.dumps(teacher_grading, ensure_ascii=False),
            ai_grading=json.dumps(ai_grading, ensure_ascii=False),
        )
        messages = [{"role": "user", "content": prompt}]
        result_text = self.llm.chat(messages, temperature=0.2)
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            result = {"raw_response": result_text}
        if result.get("suggested_rubric_revisions"):
            self._save_rubric(result["suggested_rubric_revisions"], "rubric_latest.md")
        return result

    def _save_rubric(self, content, filename):
        path = os.path.join(self.output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def generate_structured(self, criteria_doc):
        prompt = STRUCT_RUBRIC_PROMPT.format(doc=criteria_doc)
        data = _extract_json(self.llm.chat([{"role": "user", "content": prompt}], temperature=0.2))
        criteria = data.get("criteria") or []
        invalid = [c.get("name", "?") for c in criteria if not str(c.get("doc_ref", "")).strip()]
        if not criteria or invalid:
            raise ValueError(f"LLM 生成的维度缺少标准文档位置（doc_ref）：{invalid or '无有效维度'}")
        from nodes.rubric_io import normalize_weights, new_criterion
        normalized = []
        for c in criteria:
            normalized.append(new_criterion(c.get("name", ""), c.get("weight", 0), c.get("mechanical", False),
                                            c.get("doc_ref", ""), c.get("levels"), c.get("rules")))
        return {"criteria": normalize_weights(normalized)}

    def generate_row(self, criteria_doc, name):
        prompt = ROW_PROMPT.format(doc=criteria_doc, name=name)
        data = _extract_json(self.llm.chat([{"role": "user", "content": prompt}], temperature=0.2))
        if not str(data.get("doc_ref", "")).strip():
            raise ValueError(f"维度「{name}」生成失败：LLM 未给出标准文档位置")
        from nodes.rubric_io import new_criterion
        return new_criterion(data.get("name", name), data.get("weight", 0), data.get("mechanical", False),
                             data.get("doc_ref", ""), data.get("levels"), data.get("rules"))

    def generate_cells(self, criteria_doc, name, context, fields):
        prompt = CELL_PROMPT.format(
            doc=criteria_doc, name=name,
            context=json.dumps(context, ensure_ascii=False),
            fields=", ".join(fields),
        )
        return _extract_json(self.llm.chat([{"role": "user", "content": prompt}], temperature=0.2))

    def validate_deviation(self, criteria_doc, rubric):
        from nodes.rubric_io import criteria_to_markdown
        prompt = DEVIATION_PROMPT.format(doc=criteria_doc, rubric=criteria_to_markdown(rubric))
        data = _extract_json(self.llm.chat([{"role": "user", "content": prompt}], temperature=0.2))
        return data.get("warnings", [])

STRUCT_RUBRIC_PROMPT = """你是评估设计专家。依据评分标准文档生成结构化评分细则（JSON）。

## 评分标准文档（唯一事实来源）
{doc}

## 硬性要求
1. 每个评分维度对应文档的一个章节，权重沿用文档的分值占比（合计 100）
2. doc_ref 必填：必须指向该维度在文档中的具体位置（章节名/条款号），指向不了的维度不许输出
3. 禁止出现「整体质量」「是否合理」「是否完整」等无判据条目；每级描述必须是可核对的具体判据（描述性语言，禁止评价词）
4. mechanical 仅当该维度能靠正则/数值比较客观判定时才为 true，并给出 rules；否则 false、rules 为 null
5. rules 仅支持两种：
   {{"type": "exists", "pattern": "正则"}}
   {{"type": "numeric_compare", "pattern": "含捕获组的正则", "op": "<|<=|>|>=|==", "threshold": 数值}}

## 输出格式（不要代码围栏）
{{
  "criteria": [
    {{"name": "...", "weight": 10, "mechanical": false, "doc_ref": "文档章节名",
      "levels": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "rules": null}}
  ]
}}"""

ROW_PROMPT = """你是评估设计专家。为维度「{name}」生成评分细则行，依据评分标准文档。

## 评分标准文档
{doc}

## 硬性要求（同全局规范）
doc_ref 必填且指向文档具体位置；禁止无判据表述；mechanical 仅当可正则/数值判定时为 true 并给 rules；levels 为 A/B/C/D 四级描述性语言。

## 输出（不要代码围栏）
{{"name": "{name}", "weight": 10, "mechanical": false, "doc_ref": "...", "levels": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "rules": null}}"""

CELL_PROMPT = """你是评估设计专家。依据评分标准文档，只为维度「{name}」补全下列空缺字段，其余内容不要改写。

## 评分标准文档（唯一事实来源）
{doc}

## 该行已有内容（仅供参考）
{context}

## 待补全字段
{fields}

## 硬性要求
doc_ref 必须指向文档具体位置（章节名/条款号）；等级描述用可核对的具体判据（描述性语言），禁止「整体质量」「是否合理」「是否完整」等无判据表述；weight 为 0-100 的数字。

## 输出 JSON（不要代码围栏，只含待补全字段）
{{"weight": 10, "doc_ref": "...", "levels": {{"A": "...", "B": "..."}}}}"""

DEVIATION_PROMPT = """你是评估审核员。对比教师手改后的评分细则与原始标准文档，只找「实质性出入」，不评价风格。

## 原始标准文档
{doc}

## 教师手改后的细则
{rubric}

## 输出 JSON（不要围栏）
{{"warnings": [{{"criterion": "...", "message": "出入点与建议"}}]}}
出入不大时 warnings 为空数组。"""
