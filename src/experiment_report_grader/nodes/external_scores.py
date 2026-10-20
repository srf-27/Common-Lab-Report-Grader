"""课外维度成绩单：与报告评分分开存放，读取时合并回结果。

成绩单结构：{"file": "xx.xlsx", "at": 1690000000,
            "scores": {"课堂表现": {"2023010101": 88}}, "raw": {...}}
键优先用学号，其次姓名；分数统一为百分制。
"""

import json
import os


def path_for(session_dir):
    return os.path.join(session_dir, "external_scores.json")


def load(session_dir):
    try:
        with open(path_for(session_dir), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) and isinstance(data.get("scores"), dict) else {}
    except (OSError, ValueError):
        return {}


def save(session_dir, data):
    os.makedirs(session_dir, exist_ok=True)
    target = path_for(session_dir)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, target)


def apply_to_results(results, rubric, external, student_of):
    """把成绩单写回各结果的 grading.scores，并重算小计；返回写入条数。"""
    from .rubric_io import compute_subtotals

    excluded = {c["name"] for c in rubric.get("criteria", []) if c.get("excluded")}
    table = (external or {}).get("scores") or {}
    source = (external or {}).get("file") or "成绩单导入"
    touched = 0
    for result in results:
        grading = result.get("grading") or {}
        scores = grading.get("scores")
        if not isinstance(scores, dict):
            continue
        changed = False
        for name in list(scores):
            if scores[name].get("external") and name not in excluded:
                del scores[name]
                changed = True
        if result.get("status") != "graded":
            continue
        student = student_of(result.get("report_id")) or {}
        for name in excluded:
            values = table.get(name) or {}
            hit = next((values[key] for key in (student.get("学号"), student.get("姓名"))
                        if key and key in values), None)
            if hit is None:
                continue
            scores[name] = {"level": None, "score": hit, "external": True, "evidence": source}
            touched += 1
            changed = True
        if changed:
            grading["subtotals"] = compute_subtotals(scores, rubric)
            result["grading"] = grading
    return touched


def summary(external):
    if not external:
        return {"file": "", "at": 0, "dimensions": {}}
    return {"file": external.get("file") or "",
            "at": external.get("at") or 0,
            "dimensions": {name: len(values or {})
                           for name, values in (external.get("scores") or {}).items()}}
