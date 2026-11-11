"""维度补全：保存过空值的字段必须补，不能静默忽略。"""
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiment_report_grader.nodes.rubric_generator import RubricGenerator
from real_llm import client


class _RetryLLM:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, temperature=0.2, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return json.dumps({"weight": 10, "levels": {"A": "已填"}}, ensure_ascii=False)
        return json.dumps({"doc_ref": "第三章", "levels": {"B": "补上的 B"}},
                          ensure_ascii=False)


class _StubbornLLM:
    def chat(self, messages, temperature=0.2, **kwargs):
        return json.dumps({"levels": {"A": "只有 A"}}, ensure_ascii=False)


def test_generate_cells_retries_missing_fields():
    llm = _RetryLLM()
    filled = RubricGenerator(llm_client=llm).generate_cells(
        "标准原文", "误差分析", {"levels": {"A": ""}}, ["A", "B", "doc_ref"])
    assert llm.calls == 2, "缺字段应重试一次"
    assert filled["doc_ref"] == "第三章"
    assert filled["levels"]["A"] == "已填"
    assert filled["levels"]["B"] == "补上的 B"


def test_generate_cells_raises_when_still_missing():
    try:
        RubricGenerator(llm_client=_StubbornLLM()).generate_cells(
            "标准原文", "误差分析", {}, ["A", "B"])
    except ValueError as exc:
        assert "B" in str(exc)
    else:
        raise AssertionError("缺字段应报错，不能静默返回")


def test_generate_cells_real_llm_fills():
    """真模型端到端：给清晰标准原文，补全缺失的 A/B 两档判据。"""
    doc = ("误差分析章节：A 类不确定度按贝塞尔公式计算，B 类按仪器允差估算，"
           "两者合成得总不确定度并写出置信概率；只做定性描述视为不合格。")
    filled = RubricGenerator(llm_client=client()).generate_cells(
        doc, "误差分析", {"levels": {"A": "", "B": ""}}, ["A", "B"])
    assert str(filled["levels"]["A"]).strip(), filled
    assert str(filled["levels"]["B"]).strip(), filled


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("rubric cells ok")
