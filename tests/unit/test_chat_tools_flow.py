"""chat 的 tools 调用循环与 /api/flow、/flow/config（全部 fake，不打真实模型）。"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import experiment_report_grader.utils.llm_client as lc
from experiment_report_grader.utils.llm_client import LLMClient
from experiment_report_grader.web import state as state_mod


class Msg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class Call:
    def __init__(self, id, name, args):
        self.id = id
        self.function = type("F", (), {"name": name, "arguments": args})()
        self.tool_calls = None

    def model_dump(self):
        return {"id": self.id, "type": "function",
                "function": {"name": self.function.name, "arguments": self.function.arguments}}


class Resp:
    def __init__(self, message):
        self.choices = [type("C", (), {"message": message})()]


def _client(script):
    """script: 每次 create 返回的 Resp 序列；记录收到的 kwargs。"""
    client = LLMClient({"llm": {"backend": "openai",
                                "openai": {"api_key": "K", "base_url": "", "model": "m"}}})
    seen = []

    class SDK:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    seen.append(kwargs)
                    item = script.pop(0)
                    return item

    real = lc.openai_client
    lc.openai_client = lambda key, base_url, timeout=300: SDK
    return client, seen, real


def test_tools_loop_executes_and_finishes():
    calls = [Call("t1", "calc_eval", json.dumps({"expression": "6*7"}))]
    script = [Resp(Msg(tool_calls=calls)), Resp(Msg(content=json.dumps({"ok": True})))]
    client, seen, real = _client(script)
    try:
        out = client.chat([{"role": "user", "content": "q"}], tools=[{"type": "function"}],
                          tool_executor=lambda name, args: {"value": 42})
    finally:
        lc.openai_client = real
    assert json.loads(out)["ok"] is True
    assert seen[0]["tools"] and seen[1]["messages"][-1]["role"] == "tool"
    assert json.loads(seen[1]["messages"][-1]["content"])["value"] == 42


def test_tools_unsupported_gateway_degrades():
    client = LLMClient({"llm": {"backend": "openai",
                                "openai": {"api_key": "K", "base_url": "", "model": "m"}}})

    class SDK:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    if kwargs.get("tools"):
                        raise RuntimeError("tools not supported")
                    return Resp(Msg(content="普通回答"))

    real = lc.openai_client
    lc.openai_client = lambda key, base_url, timeout=300: SDK
    try:
        out = client.chat([{"role": "user", "content": "q"}], tools=[{"type": "function"}],
                          tool_executor=lambda name, args: {})
    finally:
        lc.openai_client = real
    assert out == "普通回答"


def test_max_tokens_override():
    script = [Resp(Msg(content="ok"))]
    client, seen, real = _client(script)
    try:
        client.chat([{"role": "user", "content": "q"}], max_tokens=16384)
    finally:
        lc.openai_client = real
    assert seen[0]["max_tokens"] == 16384


def _session(tmp):
    import experiment_report_grader.app as app_mod
    real = (state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR)
    state_mod.OUTPUT_FOLDER = tmp
    state_mod.SESSIONS_DIR = os.path.join(tmp, "sessions")
    os.makedirs(state_mod.SESSIONS_DIR, exist_ok=True)
    state_mod.hydrate_session(state_mod.new_session("流程测试")["id"])
    return app_mod.app.test_client(), real


def test_flow_api_and_config():
    tmp = tempfile.mkdtemp(prefix="erg_flow_")
    client, real = _session(tmp)
    try:
        payload = client.get("/api/flow").get_json()
        ids = [n["id"] for n in payload["nodes"]]
        assert ids[:3] == ["extract", "rubric", "pilot"] and "grade" in ids
        assert all(n["status"] == "pending" for n in payload["nodes"])
        # 非可插拔节点 → 400；白名单外工具被过滤
        assert client.post("/flow/config", json={"node": "rubric", "skills": ["x"]}).status_code == 400
        # 白名单过滤：calc 通过、未知项剔除；提示词式 skills 已废弃（真正能力走 skill:/mcp:）
        resp = client.post("/flow/config", json={
            "node": "grade", "tools": ["calc", "hack", "skill:chem_calc", "mcp:ghost"]})
        assert resp.status_code == 200
        cfg = resp.get_json()["config"]["grade"]
        assert cfg["tools"] == ["calc", "skill:chem_calc"], cfg
        assert "skills" not in cfg
        # 持久化 + /api/flow 暴露
        got = client.get("/api/flow").get_json()["config"]["grade"]["tools"]
        assert got == ["calc", "skill:chem_calc"]
    finally:
        state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR = real
        state_mod.hydrate_session(state_mod.load_sessions()["current"])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_chat_tools_flow ok")
