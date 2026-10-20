"""双文件细则：非报告维度也要保留，交给用户停用。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.nodes.rubric_generator import RubricGenerator


class _LLM:
    def chat(self, messages, temperature=0):
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


if __name__ == "__main__":
    test_pair_keeps_non_report_dimensions()
    print("ok")
