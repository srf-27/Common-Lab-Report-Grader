"""机械判决生成与执行：规则回退、静态校验、沙箱执行。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.nodes import verifier


class LLM:
    def __init__(self, code):
        self.code = code

    def chat(self, messages, temperature=0):
        return self.code


def test_rule_exists():
    assert verifier.verify("本文给出不确定度", {"type": "exists", "pattern": "不确定度"})["passed"] is True
    assert verifier.verify("没有", {"type": "exists", "pattern": "不确定度"})["passed"] is False


def test_rule_numeric():
    rules = {"type": "numeric_compare", "pattern": r"偏差\s*([\d.]+)%", "op": "<=", "threshold": 5}
    assert verifier.verify("相对偏差 2.4%", rules)["passed"] is True
    assert verifier.verify("相对偏差 8.1%", rules)["passed"] is False
    assert verifier.verify("没写数值", rules)["passed"] is False


def test_rule_unsupported_falls_back():
    out = verifier.verify("文本", {"type": "weird"})
    assert out["verdict"] == "unsupported" and out["passed"] is None
    assert verifier.verify("文本", None)["verdict"] == "unsupported"


def test_generate_and_run():
    code = verifier.generate([{"name": "机械项"}], LLM(
        "```python\nimport re\n\ndef verify(text):\n"
        "    return {'机械项': {'passed': bool(re.search('误差', text)), 'detail': 'x'}}\n```"))
    assert "def verify" in code
    assert verifier.run(code, "误差分析")["机械项"]["passed"] is True
    assert verifier.run(code, "无关")["机械项"]["passed"] is False


def test_validate_blocks_dangerous_code():
    for bad in ("import os\ndef verify(t): return {}", "def verify(t):\n    return eval('1')",
                "def verify(t):\n    open('x')\n    return {}"):
        try:
            verifier.run(bad, "x")
            raise AssertionError(f"should reject: {bad}")
        except (ValueError, SyntaxError):
            pass


def test_generate_rejects_bad_model_output():
    try:
        verifier.generate([{"name": "x"}], LLM("import subprocess\n\ndef verify(t): return {}"))
        raise AssertionError("should reject subprocess")
    except ValueError:
        pass


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_verifier ok")
