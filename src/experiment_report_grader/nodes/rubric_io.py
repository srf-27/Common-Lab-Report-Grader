import json
import os

LEVELS = ("A", "B", "C", "D", "E")
RUBRIC_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "rubrics", "rubric_current.json")


def new_criterion(name="", weight=0, mechanical=False, doc_ref="", levels=None, rules=None):
    return {
        "name": name,
        "weight": round(weight, 2),
        "mechanical": bool(mechanical),
        "doc_ref": doc_ref,
        "levels": levels or {lv: "" for lv in LEVELS},
        "user_edited": [],
        "rules": rules,
    }


def normalize_weights(criteria):
    active = [c for c in criteria if not c.get("_deleted")]
    n = len(active)
    if n == 0:
        return criteria
    total = sum(c.get("weight", 0) for c in active)
    if total <= 0:
        for c in active:
            c["weight"] = round(100.0 / n, 2)
    else:
        for c in active:
            c["weight"] = round(c.get("weight", 0) * 100.0 / total, 2)
    drift = 100.0 - sum(c["weight"] for c in active)
    if active and abs(drift) > 0.01:
        active[0]["weight"] = round(active[0]["weight"] + drift, 2)
    return criteria


def save_rubric_json(rubric, path=None):
    path = path or RUBRIC_JSON_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rubric, f, ensure_ascii=False, indent=2)
    return path


def load_rubric_json(path=None):
    path = path or RUBRIC_JSON_PATH
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def criteria_to_markdown(rubric, title="实验报告评分细则 (Rubric)"):
    lines = [f"# {title}", "", "## 评分维度", "",
             "| 维度 | 权重 | 是否机械判决 | 标准文档位置 | A (优秀) | B (良好) | C (及格) | D (不及格) | E (未实现) |",
             "|------|------|--------------|--------------|----------|----------|----------|------------|------------|"]
    for c in rubric.get("criteria", []):
        lv = c.get("levels", {})
        lines.append(
            f"| {c['name']} | {c['weight']}% | {'是' if c.get('mechanical') else '否'} "
            f"| {c.get('doc_ref', '')} | {lv.get('A', '')} | {lv.get('B', '')} | "
            f"{lv.get('C', '')} | {lv.get('D', '')} | {lv.get('E', '')} |"
        )
    lines += ["", "## 评分说明",
              "按维度独立评分，权重加总为 100%。机械判决维度由程序按规则判分，其余由 LLM 依据描述判分；"
              "E 表示该维度内容未实现/缺失或严重不合格（未做、整卷跑题、抄袭、白卷）。"]
    return "\n".join(lines)


def rubric_weights(rubric):
    return {c["name"]: c.get("weight", 0) for c in rubric.get("criteria", [])}


LEVEL_POINTS = {"A": 95, "B": 80, "C": 60, "D": 40, "E": 0}


def compute_subtotals(scores, rubric):
    weights = rubric_weights(rubric)
    fallback = 100.0 / len(scores) if scores else 0.0
    procedural = semantic = 0.0
    mech_names = {c["name"] for c in rubric.get("criteria", []) if c.get("mechanical")}
    for criterion, detail in scores.items():
        w = weights.get(criterion, fallback)
        pts = LEVEL_POINTS.get(detail.get("level"), 0) * w / 100.0
        if criterion in mech_names:
            procedural += pts
        else:
            semantic += pts
    return {"procedural": round(procedural, 1), "semantic": round(semantic, 1),
            "total": round(procedural + semantic, 1)}


VAGUE_TERMS = ("整体质量", "是否合理", "是否完整", "总体印象", "综合表现")


def check_vague_and_refs(criteria):
    warnings = []
    for c in criteria:
        name = c.get("name", "")
        if not c.get("doc_ref", "").strip():
            warnings.append({"criterion": name, "type": "missing_ref",
                             "message": f"「{name}」未指向评分标准文档的具体位置，该条判定的可能并非本评分标准文档。建议补充标准文档位置。"})
        blob = name + "".join(c.get("levels", {}).values())
        for term in VAGUE_TERMS:
            if term in blob:
                warnings.append({"criterion": name, "type": "vague",
                                 "message": f"「{name}」含无判据表述「{term}」，建议改为可核对的具体判据。"})
                break
    return warnings
