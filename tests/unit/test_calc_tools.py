"""计算工具包：数值正确性与表达式安全边界。"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.utils import calc_tools


def test_eval_basic_and_funcs():
    assert calc_tools.calc_eval("1+1")["value"] == 2
    assert abs(calc_tools.calc_eval("2**10")["value"] - 1024) < 1e-12
    assert abs(calc_tools.calc_eval("(23.45e-6)/(4*10*589.3e-9)")["value"]
               - 23.45e-6 / (4 * 10 * 589.3e-9)) < 1e-12
    assert abs(calc_tools.calc_eval("sqrt(2)")["value"] - math.sqrt(2)) < 1e-12
    assert abs(calc_tools.calc_eval("pi")["value"] - math.pi) < 1e-12
    assert calc_tools.calc_eval("-3 + 5")["value"] == 2


def test_eval_rejects_dangerous():
    for bad in ("__import__('os')", "open('/etc/passwd')", "(1).__class__", "x",
                "'a' + 'b'", "[1,2]", "{'a':1}", "1 if True else 2", "f()", "sqrt(kw=2)"):
        try:
            calc_tools.calc_eval(bad)
            raise AssertionError(f"should reject: {bad}")
        except (ValueError, SyntaxError, TypeError):
            pass


def test_stats_known_values():
    out = calc_tools.calc_stats([1.0, 2.0, 3.0], instrument_error=0.0)
    assert abs(out["mean"] - 2.0) < 1e-12 and abs(out["std"] - 1.0) < 1e-12
    assert abs(out["ua"] - 1.0 / math.sqrt(3)) < 1e-12
    out = calc_tools.calc_stats([10.0, 10.0, 10.0], instrument_error=0.03)
    assert abs(out["ub"] - 0.03 / math.sqrt(3)) < 1e-12
    try:
        calc_tools.calc_stats([1.0])
        raise AssertionError("should reject n<2")
    except ValueError:
        pass


def test_fit_known_line():
    out = calc_tools.calc_fit([1, 2, 3, 4], [2.1, 3.9, 6.2, 7.8])
    assert abs(out["slope"] - 1.93) < 0.05
    assert out["r"] > 0.99
    try:
        calc_tools.calc_fit([1], [1])
        raise AssertionError("should reject <2 points")
    except ValueError:
        pass


def test_dispatch_and_schema_aligned():
    names = {t["function"]["name"] for t in calc_tools.TOOLS_SCHEMA}
    assert set(calc_tools._IMPL) == names == {"calc_eval", "calc_stats", "calc_fit"}
    assert calc_tools.dispatch("calc_eval", {"expression": "6*7"})["value"] == 42
    try:
        calc_tools.dispatch("nope", {})
        raise AssertionError("unknown tool should raise")
    except ValueError:
        pass
    try:
        calc_tools.dispatch("calc_fit", {"xs": [1], "ys": [1, 2]})
        raise AssertionError("mismatched lengths should raise")
    except ValueError:
        pass


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_calc_tools ok")
