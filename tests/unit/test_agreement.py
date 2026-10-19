"""一致性指标：完全一致、相邻偏差、样本不足。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.nodes.agreement import (agreement_report, band, cohen_kappa,
                                                     krippendorff_alpha, weighted_kappa)


def test_perfect_agreement():
    pairs = [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")]
    assert cohen_kappa(pairs) == 1.0
    assert weighted_kappa(pairs) == 1.0
    assert krippendorff_alpha(pairs) == 1.0


def test_adjacent_bias_tolerated():
    pairs = [("A", "A"), ("A", "B"), ("B", "B"), ("B", "C")]
    assert weighted_kappa(pairs) > cohen_kappa(pairs)


def test_insufficient_samples():
    assert cohen_kappa([]) is None
    assert krippendorff_alpha([("A", "A")]) is None


def test_band():
    assert [band(p) for p in (95, 85, 75, 65, 10)] == ["A", "B", "C", "D", "E"]


def test_report_structure():
    rubric = {"criteria": [{"name": "误差分析"}]}
    results = [{"report_id": "a.docx", "status": "graded",
                "grading": {"scores": {"误差分析": {"level": "A"}}}},
               {"report_id": "b.docx", "status": "graded",
                "grading": {"scores": {"误差分析": {"level": "B"}}}}]
    teacher = {"a.docx": {"误差分析": "A"}, "b.docx": {"误差分析": "B"}}
    report = agreement_report(results, rubric, teacher)
    assert report["overall"]["n"] == 2 and report["overall"]["cohen_kappa"] == 1.0
    assert "误差分析" in report["dimensions"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_agreement ok")
