"""维度补全：保存过空值的字段必须补，不能静默忽略。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.nodes.rubric_generator import RubricGenerator


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


if __name__ == "__main__":
    test_generate_cells_retries_missing_fields()
    test_generate_cells_raises_when_still_missing()
    print("rubric cells ok")
