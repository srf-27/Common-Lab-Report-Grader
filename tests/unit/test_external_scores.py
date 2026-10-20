"""课外维度成绩：数值分数、按学号合并、非报告维度识别。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.nodes import external_scores, rubric_io

RUBRIC = {"criteria": [
    {"name": "数据记录", "weight": 60, "mechanical": False, "doc_ref": "表1",
     "levels": {}, "rules": None},
    {"name": "课堂表现", "weight": 40, "mechanical": False, "excluded": True,
     "doc_ref": "大纲", "levels": {}, "rules": None},
]}


def test_numeric_score_subtotal():
    scores = {"数据记录": {"level": "A"}, "课堂表现": {"score": 88}}
    assert rubric_io.compute_subtotals(scores, RUBRIC)["total"] == 92.2


def test_apply_external_by_student_id():
    results = [{"report_id": "张三.docx", "status": "graded",
                "grading": {"scores": {"数据记录": {"level": "B"}}}}]
    external = {"file": "scores.csv", "scores": {"课堂表现": {"2023010101": 80}}}
    touched = external_scores.apply_to_results(
        results, RUBRIC, external, lambda _rid: {"学号": "2023010101"})
    assert touched == 1
    entry = results[0]["grading"]["scores"]["课堂表现"]
    assert entry["score"] == 80 and entry["external"] is True
    assert results[0]["grading"]["subtotals"]["total"] == 80.0


def test_non_report_detection():
    assert rubric_io.is_non_report({"name": "课堂表现"})
    assert rubric_io.is_non_report({"name": "方案设计", "doc_ref": "预习：方案设计"})
    assert not rubric_io.is_non_report({"name": "数据记录", "doc_ref": "表1"})
    assert not rubric_io.is_non_report({"name": "格式规范", "doc_ref": "自评与格式"})


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name} ok")


def test_match_criterion_short_names():
    names = ["实验目的、原理及反应体系论述", "数据处理与计算分析", "结果讨论与工艺条件分析"]
    assert rubric_io.match_criterion("实验目的与原理", names) == names[0]
    assert rubric_io.match_criterion("数据处理", names) == names[1]
    assert rubric_io.match_criterion("结果讨论", names) == names[2]
    assert rubric_io.match_criterion("完全无关的维度", names) is None
