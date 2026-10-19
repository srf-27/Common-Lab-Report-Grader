"""隐私脱敏：LLM 提取替换 + 失败时正则兜底（红线，不能漏）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.utils.privacy import anonymize_text


class LLM:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc = resp, exc

    def chat(self, messages, temperature=0):
        if self.exc:
            raise self.exc
        return self.resp


TEXT = "姓名：张三　学号：20230001　联系 zhang@example.com 电话 13800001111"


def test_llm_replaces_entities():
    llm = LLM('{"entities": [{"type": "name", "value": "张三"}, '
              '{"type": "student_id", "value": "20230001"}]}')
    out, made = anonymize_text(TEXT, llm)
    assert "张三" not in out and "20230001" not in out
    assert "[姓名已脱敏]" in out and "[学号已脱敏]" in out
    assert len(made) == 2


def test_fallback_on_llm_failure():
    for llm in (LLM(exc=RuntimeError("timeout")), LLM("不是 JSON"), None):
        out, made = anonymize_text(TEXT, llm)
        assert "张三" not in out, out
        assert "20230001" not in out, out
        assert "zhang@example.com" not in out, out
        assert "13800001111" not in out, out
        assert made


def test_longest_entity_replaced_first():
    llm = LLM('{"entities": [{"type": "name", "value": "张三"}, '
              '{"type": "address", "value": "张三宿舍 3 栋"}]}')
    out, _ = anonymize_text("住址：张三宿舍 3 栋", llm)
    assert "张三宿舍" not in out


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_privacy ok")
