"""chat_stream / ThinkingTap / thinking 滚动窗口（全部 fake，不打真实模型）。"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.utils.llm_client import LLMClient
from experiment_report_grader.web import state as state_mod
from experiment_report_grader.web import tasks as task_mod


class FakeStreamClient:
    def __init__(self, events):
        self.events = events

    def chat_stream(self, messages, temperature=0.3):
        yield from self.events

    def chat(self, messages, temperature=0.3, retries=2):
        return "fallback"


EVENTS = [
    ("thinking", "先分析维度："),
    ("thinking", "误差分析应占 40%。"),
    ("answer", '{"criteria": []}'),
    ("usage", {"prompt_tokens": 10, "completion_tokens": 5}),
]


def test_chat_stream_openai_events():
    client = LLMClient({"llm": {"backend": "openai", "openai": {
        "api_key": "K", "base_url": "", "model": "m"}}})
    client._call_openai = lambda messages, temperature: "非流式兜底"

    class Stream:
        def __iter__(self):
            yield from _chunks()

    def _chunks():
        class D:
            def __init__(self, content=None, reasoning_content=None):
                self.content = content
                self.reasoning_content = reasoning_content

        class C:
            def __init__(self, delta):
                self.choices = [type("Ch", (), {"delta": delta})()]

        yield C(D(content="答"))
        yield C(D(reasoning_content="思"))
        yield type("U", (), {"usage": type("X", (), {"prompt_tokens": 3, "completion_tokens": 2})(),
                             "choices": []})()

    client_stream = LLMClient.chat_stream
    orig = client.openai_client if hasattr(client, "openai_client") else None
    import experiment_report_grader.utils.llm_client as lc
    real_openai_client = lc.openai_client

    class FakeSDK:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    assert kwargs.get("stream") is True
                    return Stream()

    lc.openai_client = lambda key, base_url, timeout=300: FakeSDK
    try:
        events = list(client.chat_stream([{"role": "user", "content": "q"}]))
    finally:
        lc.openai_client = real_openai_client
    kinds = [k for k, _ in events]
    assert kinds == ["answer", "thinking", "usage"], kinds
    assert events[-1][1].prompt_tokens == 3


def test_chat_stream_non_openai_degrades():
    client = LLMClient({"llm": {"backend": "ollama", "ollama": {"base_url": "x", "model": "m"}}})
    client.chat = lambda messages, temperature=0.3: "一次答"
    events = list(client.chat_stream([{"role": "user", "content": "q"}]))
    assert events == [("answer", "一次答"), ("usage", {})]


def test_thinking_tap_streams_into_task():
    import experiment_report_grader.app as app_mod
    tmp = tempfile.mkdtemp(prefix="erg_tap_")
    real = (state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR)
    try:
        state_mod.OUTPUT_FOLDER = tmp
        state_mod.SESSIONS_DIR = os.path.join(tmp, "sessions")
        os.makedirs(state_mod.SESSIONS_DIR, exist_ok=True)
        t = task_mod.task_start("criteria", "/app/rubric", mode="stage", sid="s_tap")
        tap = app_mod._ThinkingTap(FakeStreamClient(EVENTS), t)
        answer = tap.chat([{"role": "user", "content": "q"}])
        assert answer == '{"criteria": []}'
        assert "误差分析" in t["thinking"]
        snapshot = os.path.join(tmp, "sessions", "s_tap", "memory", "task.json")
        import json
        saved = json.load(open(snapshot, encoding="utf-8")) if os.path.exists(snapshot) else {}
        assert "thinking" not in saved, "思考过程不落盘"
    finally:
        task_mod.RUNNING_TASKS.pop("s_tap", None)
        state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR = real


def test_thinking_window_trims_to_tail():
    tmp = tempfile.mkdtemp(prefix="erg_win_")
    real = (state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR)
    try:
        state_mod.OUTPUT_FOLDER = tmp
        state_mod.SESSIONS_DIR = os.path.join(tmp, "sessions")
        os.makedirs(state_mod.SESSIONS_DIR, exist_ok=True)
        t = task_mod.task_start("criteria", "/x", mode="stage", sid="s_win")
        for i in range(40):
            task_mod.task_update(t, thinking=f"片段{i}｜" + "字" * 30)
        assert len(t["thinking"]) <= 600
        assert "片段39" in t["thinking"] and "片段0｜" not in t["thinking"]
    finally:
        task_mod.RUNNING_TASKS.pop("s_win", None)
        state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR = real


def test_tap_falls_back_when_stream_fails():
    import experiment_report_grader.app as app_mod

    class Broken:
        def chat_stream(self, messages, temperature=0.3):
            raise RuntimeError("stream broken")
            yield  # pragma: no cover

        def chat(self, messages, temperature=0.3, retries=2):
            return "fallback"

    tmp = tempfile.mkdtemp(prefix="erg_fb_")
    real = (state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR)
    try:
        state_mod.OUTPUT_FOLDER = tmp
        state_mod.SESSIONS_DIR = os.path.join(tmp, "sessions")
        os.makedirs(state_mod.SESSIONS_DIR, exist_ok=True)
        t = task_mod.task_start("criteria", "/x", sid="s_fb")
        tap = app_mod._ThinkingTap(Broken(), t)
        assert tap.chat([{"role": "user", "content": "q"}]) == "fallback"
    finally:
        task_mod.RUNNING_TASKS.pop("s_fb", None)
        state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR = real


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_chat_stream ok")
