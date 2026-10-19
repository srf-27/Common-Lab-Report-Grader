"""细则工具：权重归一、小计、校验收紧。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.nodes import rubric_io


def _criterion(name, weight, mechanical=False):
    return rubric_io.new_criterion(name, weight, mechanical, "第一章")


def test_normalize_weights_sums_to_100():
    criteria = [_criterion("a", 30), _criterion("b", 30)]
    out = rubric_io.normalize_weights(criteria)
    assert [c["weight"] for c in out] == [50.0, 50.0], out


def test_normalize_weights_zero_and_single():
    zero = rubric_io.normalize_weights([_criterion("a", 0), _criterion("b", 0), _criterion("c", 0)])
    assert [round(c["weight"], 2) for c in zero] == [33.34, 33.33, 33.33], zero
    assert abs(sum(c["weight"] for c in zero) - 100) < 0.01
    single = rubric_io.normalize_weights([_criterion("only", 7)])
    assert single[0]["weight"] == 100.0


def test_normalize_skips_deleted():
    out = rubric_io.normalize_weights([_criterion("a", 1), {"name": "x", "_deleted": True}])
    assert out[0]["weight"] == 100.0


def test_compute_subtotals_splits_mechanical():
    rubric = {"criteria": [_criterion("mech", 40, True), _criterion("sem", 60)]}
    scores = {"mech": {"level": "A"}, "sem": {"level": "C"}}
    out = rubric_io.compute_subtotals(scores, rubric)
    assert out == {"procedural": 38.0, "semantic": 36.0, "total": 74.0}, out


def test_check_vague_and_refs():
    warnings = rubric_io.check_vague_and_refs([
        {"name": "整体质量", "doc_ref": "", "levels": {"A": "好"}},
        {"name": "数据处理", "doc_ref": "第四章", "levels": {"A": "逐差法计算"}},
    ])
    types = {w["type"] for w in warnings}
    assert "missing_ref" in types and "vague" in types
    assert len(rubric_io.check_vague_and_refs([{"name": "数据处理", "doc_ref": "第四章",
                                               "levels": {"A": "逐差法计算"}}])) == 0


def test_markdown_roundtrip():
    rubric = {"criteria": [_criterion("误差分析", 100)]}
    md = rubric_io.criteria_to_markdown(rubric)
    assert "| 误差分析 | 100% |" in md
    assert "E (未实现)" in md


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_rubric_io ok")
