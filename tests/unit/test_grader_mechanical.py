"""机械判决 × Grader 集成边界：生成 / 执行 / 异常 / 回退全路径（不打真实模型）。

覆盖此前从未测试的路径：verifier 代码由 LLM 生成后经沙箱执行的完整链路。
"""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.nodes.grader import Grader

VERIFIER_OK = (
    "import re\n\n"
    "def verify(text):\n"
    "    results = {}\n"
    "    results['机械项'] = {'passed': bool(re.search('不确定度', text)), 'detail': '查不确定度'}\n"
    "    results['半机械项'] = {'passed': None, 'detail': '证据不足'}\n"
    "    return results\n"
)
VERIFIER_RAISES = "def verify(text):\n    raise RuntimeError('boom')\n"
VERIFIER_BAD_CODE = "import subprocess\n\ndef verify(t): return {}"  # 静态校验直接拒绝


class LLM:
    """按提示词内容分流：机械判决生成 → 返回代码；语义判级 → 返回分数 JSON。"""

    def __init__(self, verifier_reply):
        self.verifier_reply = verifier_reply
        self.calls = []

    def chat(self, messages, temperature=0.3, retries=2):
        prompt = "".join(str(m.get("content", "")) for m in messages)
        self.calls.append(prompt[:30])
        if "机械判决器作者" in prompt:
            return self.verifier_reply
        return json.dumps({
            "scores": {"语义项": {"level": "B", "evidence": "证据", "reasoning": "理由"},
                       "半机械项": {"level": "C", "evidence": "语义兜底", "reasoning": "规则不支持"}},
            "summary": "总评", "flags": []}, ensure_ascii=False)


def _rubric():
    return {"criteria": [
        {"name": "机械项", "weight": 60, "mechanical": True, "levels": {},
         "rules": {"type": "exists", "pattern": "不确定度"}},
        # 机械项但 rules 类型不支持：verifier 与 rules 都无法判 → 回退语义
        {"name": "半机械项", "weight": 20, "mechanical": True, "levels": {},
         "rules": {"type": "weird"}},
        {"name": "语义项", "weight": 20, "mechanical": False, "levels": {}},
    ]}


def _grader(verifier_reply, tmp):
    return Grader(_rubric(), llm_client=LLM(verifier_reply), config={},
                  output_dir=os.path.join(tmp, "grading"), kb_session_dir=tmp)


TEXT_HIT = "本文给出不确定度 u=0.005m。"
TEXT_MISS = "没有任何相关内容。"


def test_verifier_ok_scores_and_semantic_fallback():
    tmp = tempfile.mkdtemp(prefix="erg_mech_")
    g = _grader(VERIFIER_OK, tmp)
    scores, fallback = g._verify_mechanical(TEXT_HIT)
    assert scores["机械项"]["level"] == "A" and scores["机械项"]["mechanical"] is True
    assert scores["机械项"]["evidence"] == "查不确定度"
    # 未命中 → D（E 只留给缺失/跑题，机械判决不产 E）
    scores2, _ = g._verify_mechanical(TEXT_MISS)
    assert scores2["机械项"]["level"] == "D"
    # passed=None → rules 兜底；rules 不支持 → 回退语义
    assert "半机械项" in [c["name"] for c in fallback] and "半机械项" not in scores
    assert g.verifier_code and "def verify" in g.rubric["verifier_code"]  # 随 rubric 保存


def test_verifier_runtime_error_falls_back_to_rules():
    tmp = tempfile.mkdtemp(prefix="erg_mech_")
    g = _grader(VERIFIER_RAISES, tmp)
    scores, fallback = g._verify_mechanical(TEXT_HIT)
    assert "执行失败" in g.verifier_error
    assert scores["机械项"]["level"] == "A" and scores["机械项"]["mechanical"] is True
    assert "半机械项" in [c["name"] for c in fallback]


def test_verifier_generation_failure_uses_rules():
    tmp = tempfile.mkdtemp(prefix="erg_mech_")
    g = _grader(VERIFIER_BAD_CODE, tmp)
    scores, fallback = g._verify_mechanical(TEXT_HIT)
    assert "生成失败" in g.verifier_error
    assert g.verifier_code == ""
    assert scores["机械项"]["level"] == "A"  # rules exists 命中
    assert "半机械项" in [c["name"] for c in fallback]


def test_verifier_passed_none_uses_rules_result():
    tmp = tempfile.mkdtemp(prefix="erg_mech_")
    code = ("def verify(text):\n"
            "    return {'机械项': {'passed': None, 'detail': '不确定'}, "
            "'半机械项': {'passed': None, 'detail': '不确定'}}")
    g = _grader(code, tmp)
    scores, fallback = g._verify_mechanical(TEXT_HIT)
    # 机械项：verifier None → rules exists 命中 → A；半机械项：rules 不支持 → 回退
    assert scores["机械项"]["level"] == "A"
    assert "半机械项" in [c["name"] for c in fallback]


def test_grade_single_mechanical_end_to_end():
    """完整判级链路（预置检测缓存绕过注入/安全 LLM 调用）：机械项由程序给分。"""
    tmp = tempfile.mkdtemp(prefix="erg_mech_")
    g = _grader(VERIFIER_OK, tmp)
    digest = hashlib.sha256(TEXT_HIT.encode("utf-8")).hexdigest()
    g._checks_cache = {
        f"injection:{digest}": {"is_injection": False},
        f"safety:{digest}": {"verdict": "allow", "warned": []},
    }
    outcome = g.grade_single("r1", TEXT_HIT)
    result = outcome["result"]
    assert result["status"] == "graded", result
    scores = result["grading"]["scores"]
    assert scores["机械项"]["level"] == "A" and scores["机械项"].get("mechanical") is True
    assert scores["语义项"]["level"] == "B"
    assert scores["半机械项"]["level"] == "C"  # 回退语义后由 LLM 给出
    # 机械项不进语义提示词：语义调用只覆盖 fallback + 非机械维度
    assert result["grading"]["subtotals"]["total"] > 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_grader_mechanical ok")
