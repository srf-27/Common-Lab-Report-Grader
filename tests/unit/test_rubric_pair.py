"""双文件细则：非报告维度也要保留，交给用户停用。"""
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from experiment_report_grader.nodes.rubric_generator import RubricGenerator
from real_llm import client


class _LLM:
    def chat(self, messages, temperature=0, **kwargs):
        return json.dumps({"criteria": [
            {"name": "数据处理", "weight": 70, "doc_ref": "大纲九；步骤 3",
             "levels": {k: k for k in "ABCDE"}, "mechanical": False, "non_report": False},
            {"name": "预习报告", "weight": 30, "doc_ref": "大纲九；预习",
             "levels": {k: k for k in "ABCDE"}, "mechanical": False, "non_report": True},
        ], "ignored": []}, ensure_ascii=False)


def test_pair_keeps_non_report_dimensions():
    result = RubricGenerator(llm_client=_LLM()).generate_structured_pair("大纲", "实验流程")
    names = [item["name"] for item in result["criteria"]]
    assert names == ["数据处理", "预习报告"]
    pre = next(item for item in result["criteria"] if item["name"] == "预习报告")
    assert pre["non_report"] is True
    assert pre["excluded"] is True, "非报告维度保留但默认停用，用户可取消"
    assert result["criteria"][0]["excluded"] is False


def test_pair_real_llm_structures_criteria():
    """真模型端到端：真实大纲+流程 → 结构化维度，名称非空、五档判据齐全、不含 rules（C2）。"""
    syllabus = ("课程考核：实验报告占 60 分，其中数据处理与误差分析 40 分、实验原理与步骤论述 20 分；"
                "预习报告占 10 分，课堂表现占 10 分。")
    flow = ("实验目的：用单摆测定重力加速度。步骤：1 组装单摆；2 测量摆长与周期；"
            "3 用逐差法处理数据；4 计算 A 类与 B 类不确定度并合成，给出置信概率。")
    result = RubricGenerator(llm_client=client()).generate_structured_pair(syllabus, flow)
    criteria = result.get("criteria")
    assert isinstance(criteria, list) and criteria, result
    for item in criteria:
        assert str(item.get("name", "")).strip(), item
        assert set(item.get("levels") or {}) >= set("ABCDE"), item
        assert "rules" not in item, item


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("test_rubric_pair ok")
