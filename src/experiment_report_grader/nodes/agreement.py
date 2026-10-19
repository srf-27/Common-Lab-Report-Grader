"""AI 与教师等级的一致性分析：Cohen's κ、二次加权 κ、Krippendorff's α（按维度 + 总体）。"""

import json
import os

from .rubric_io import LEVELS

_POINTS = {level: len(LEVELS) - 1 - index for index, level in enumerate(LEVELS)}


def _clean(pairs):
    return [(a, t) for a, t in pairs if a in _POINTS and t in _POINTS]


def _dist(x, y):
    # 等级秩上的二次距离，与二次加权 κ 的权重一致
    return ((_POINTS[x] - _POINTS[y]) / (len(LEVELS) - 1)) ** 2


def cohen_kappa(pairs):
    """未加权 Cohen's κ；样本为空或期望一致率≥1 时返回 None。"""
    pairs = _clean(pairs)
    n = len(pairs)
    if n == 0:
        return None
    a_counts = {level: 0 for level in LEVELS}
    t_counts = {level: 0 for level in LEVELS}
    agree = 0
    for a, t in pairs:
        a_counts[a] += 1
        t_counts[t] += 1
        agree += a == t
    pe = sum(a_counts[level] * t_counts[level] for level in LEVELS) / n ** 2
    if pe >= 1:
        return None
    return (agree / n - pe) / (1 - pe)


def weighted_kappa(pairs):
    """二次加权的 Cohen's κ；样本为空返回 None。"""
    pairs = _clean(pairs)
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(1 - _dist(a, t) for a, t in pairs) / n
    ai_counts = {level: 0 for level in LEVELS}
    teacher_counts = {level: 0 for level in LEVELS}
    for a, t in pairs:
        ai_counts[a] += 1
        teacher_counts[t] += 1
    expected = sum(ai_counts[x] / n * teacher_counts[y] / n * (1 - _dist(x, y))
                   for x in LEVELS for y in LEVELS)
    if expected >= 1:
        return 1.0
    return (observed - expected) / (1 - expected)


def krippendorff_alpha(pairs):
    """Krippendorff's α（等级秩二次距离，两位评分者完全数据）；样本 <2 或无期望分歧返回 None。"""
    pairs = _clean(pairs)
    n = len(pairs)
    if n < 2:
        return None
    counts = {level: 0 for level in LEVELS}
    for a, t in pairs:
        counts[a] += 1
        counts[t] += 1
    observed = sum(_dist(a, t) for a, t in pairs) / n
    total = 2 * n
    expected = sum(counts[x] * counts[y] * _dist(x, y)
                   for x in LEVELS for y in LEVELS if x != y) / (total * (total - 1))
    if expected == 0:
        return None
    return 1 - observed / expected


def _metrics(pairs):
    def clean(v):
        return 0.0 if v is not None and abs(v) < 5e-13 else v
    return {"cohen_kappa": clean(cohen_kappa(pairs)),
            "weighted_kappa": clean(weighted_kappa(pairs)),
            "krippendorff_alpha": clean(krippendorff_alpha(pairs)),
            "n": len(pairs)}


def _pairs_for(results, criterion, teacher_grades):
    pairs, confusion = [], {}
    for result in results:
        if result.get("status") != "graded":
            continue
        entry = ((result.get("grading") or {}).get("scores") or {}).get(criterion) or {}
        ai_level = entry.get("ai_level") or entry.get("level")
        teacher_level = (teacher_grades.get(result["report_id"]) or {}).get(criterion)
        if not teacher_level and entry.get("teacher_adjusted"):
            teacher_level = entry.get("level")
        if ai_level and teacher_level:
            pairs.append((ai_level, teacher_level))
            key = f"{ai_level}->{teacher_level}"
            confusion[key] = confusion.get(key, 0) + 1
    return pairs, confusion


def band(percent):
    """百分制总分 → A-E 档位。"""
    return "A" if percent >= 90 else "B" if percent >= 80 else \
           "C" if percent >= 70 else "D" if percent >= 60 else "E"


def _band_pairs(results, teacher_grades):
    pairs, confusion = [], {}
    for r in results:
        if r.get("status") != "graded":
            continue
        total = ((r.get("grading") or {}).get("subtotals") or {}).get("total")
        t = (teacher_grades.get(r["report_id"]) or {}).get("总分")
        if total is None or not t:
            continue
        pairs.append((band(total), t))
        key = f"{band(total)}->{t}"
        confusion[key] = confusion.get(key, 0) + 1
    return pairs, confusion


def agreement_report(results, rubric, teacher_grades=None):
    """返回 {overall: {三项指标, n}, dimensions: {维度: {三项指标, n, confusion}}}。

    教师真值只有总分档（如外部基准）时，额外给出「总分档位」行，并作为 overall 兜底。
    """
    teacher_grades = teacher_grades or {}
    names = [c["name"] for c in rubric.get("criteria", [])]
    dimensions, all_pairs = {}, []
    for name in names:
        pairs, confusion = _pairs_for(results, name, teacher_grades)
        all_pairs += pairs
        dimensions[name] = dict(_metrics(pairs), confusion=confusion)
    band_pairs, band_confusion = _band_pairs(results, teacher_grades)
    if band_pairs:
        dimensions["总分档位"] = dict(_metrics(band_pairs), confusion=band_confusion)
    overall = _metrics(all_pairs if all_pairs else band_pairs)
    return {"overall": overall, "dimensions": dimensions}


def teacher_grades_path(session_dir):
    return os.path.join(session_dir, "teacher_grades.json")


def load_teacher_grades(session_dir):
    path = teacher_grades_path(session_dir)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}
