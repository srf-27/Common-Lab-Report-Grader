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


# ---------------- 边界用例（2026-10 详细测试补齐） ----------------
def test_validate_import_from_rejected():
    try:
        verifier.run("from os import system\n\ndef verify(t): return {}", "x")
        raise AssertionError("should reject from-import")
    except (ValueError, SyntaxError):
        pass


def test_validate_dunder_attribute_rejected():
    try:
        verifier._validate("def verify(t):\n    return t.__class__")
        raise AssertionError("should reject dunder attribute")
    except ValueError:
        pass


def test_validate_allows_safe_imports_and_names():
    code = ("import re\nimport json\nimport math\n\n"
            "def verify(text):\n"
            "    return {'a': {'passed': bool(re.search('x', text)), 'detail': str(len(text))}}")
    verifier._validate(code)
    verifier.run(code, "xx")


def test_validate_rejects_syntax_error():
    try:
        verifier._validate("def verify(t:  return {}")
        raise AssertionError("should reject syntax error")
    except SyntaxError:
        pass


def test_validate_rejects_forbidden_names():
    for name in ("getattr", "compile", "input", "vars"):
        code = f"def verify(t):\n    return {name}('x')"
        try:
            verifier._validate(code)
            raise AssertionError(f"should reject {name}")
        except ValueError:
            pass


def test_run_requires_verify_function():
    try:
        verifier.run("x = 1", "text")
        raise AssertionError("should reject code without verify")
    except ValueError:
        pass


def test_run_requires_dict_result():
    try:
        verifier.run("def verify(t):\n    return [1, 2]", "text")
        raise AssertionError("should reject non-dict result")
    except ValueError:
        pass


def test_run_propagates_verify_exception():
    try:
        verifier.run("def verify(t):\n    raise RuntimeError('boom')", "text")
        raise AssertionError("verify 内部异常应向上传播，由 grader 捕获回退")
    except RuntimeError:
        pass


def test_rule_bad_pattern_is_unsupported():
    assert verifier.verify("文本", {"type": "exists", "pattern": "("})["verdict"] == "unsupported"


def test_rule_bad_threshold_and_op():
    rules = {"type": "numeric_compare", "pattern": r"([\d.]+)", "op": "<=", "threshold": "abc"}
    assert verifier.verify("偏差 3%", rules)["verdict"] == "unsupported"
    rules = {"type": "numeric_compare", "pattern": r"([\d.]+)", "op": "~", "threshold": 5}
    assert verifier.verify("偏差 3%", rules)["verdict"] == "unsupported"


def test_rule_multi_mixed_unsupported():
    rules = [{"type": "exists", "pattern": "不确定度"}, {"type": "weird"}]
    out = verifier.verify("含不确定度", rules)
    assert out["verdict"] == "unsupported" and out["passed"] is None


def test_rule_non_list_rules():
    assert verifier.verify("文本", "not-a-list")["verdict"] == "unsupported"
    assert verifier.verify("文本", [])["verdict"] == "unsupported"


def test_rule_numeric_missing_capture_group():
    rules = {"type": "numeric_compare", "pattern": r"\d+", "op": "<=", "threshold": 5}
    out = verifier.verify("偏差 3%", rules)  # 模式无捕获组 → group(1) IndexError → unsupported
    assert out["verdict"] == "unsupported"
