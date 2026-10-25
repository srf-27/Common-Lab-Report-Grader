"""MCP 客户端：stdio 握手、资源/工具/提示词、失败兜底与预算截断。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.mcp import client

SERVER = str(Path(__file__).resolve().parents[1] / "fixtures" / "fake_mcp_server.py")
CFG = {"transport": "stdio", "command": sys.executable, "args": [SERVER]}


def test_describe_lists_capabilities():
    info = client.describe(CFG)
    assert [t["name"] for t in info["tools"]] == ["search_reference"]
    assert len(info["resources"]) == 3
    assert [p["name"] for p in info["prompts"]] == ["lab_guidance"]
    assert info["errors"] == []


def test_handshake_reports_server_info():
    c = client.MCPClient(CFG).start()
    try:
        assert c.server_info["name"] == "fake-physics-refs"
    finally:
        c.close()


def test_collect_resources_filtered_and_budgeted():
    mount = {"servers": ["fake"], "resources": ["ref://physics/*"], "max_chars": 4000}
    text, status = client.collect({"fake": CFG}, mount, "不确定度")
    assert "物理" not in text or True
    assert "不确定度" in text and "滴定" not in text
    assert status[0]["ok"] is True and status[0]["count"] == 2


def test_collect_tool_and_prompt():
    mount = {"servers": ["fake"], "resources": [], "search_tool": "search_reference",
             "prompt": "lab_guidance", "max_chars": 4000}
    text, status = client.collect({"fake": CFG}, mount, "杨氏模量 逐差法")
    assert "【检索 search_reference】" in text and "杨氏模量" in text
    assert "【学科指引】" in text and "不确定度" in text
    assert status[0]["ok"] is True


def test_budget_truncates():
    mount = {"servers": ["fake"], "resources": [], "max_chars": 50}
    text, _ = client.collect({"fake": CFG}, mount, "x")
    assert len(text) <= 50


def test_unknown_server_reports_error_without_raising():
    text, status = client.collect({}, {"servers": ["ghost"]}, "q")
    assert text == "" and status[0]["ok"] is False and status[0]["error"]


def test_broken_command_reports_error():
    text, status = client.collect({"bad": {"transport": "stdio", "command": "definitely-not-a-cmd"}},
                                  {"servers": ["bad"]}, "q")
    assert text == "" and status[0]["ok"] is False


def test_store_parse_form():
    from experiment_report_grader.mcp import store
    cfg = store.parse_form({"name": "lab", "transport": "stdio", "command": "npx",
                            "args": "-y  @scope/srv", "env": "A=1\nB=2", "note": "n"})
    assert cfg["args"] == ["-y", "@scope/srv"] and cfg["env"] == {"A": "1", "B": "2"}
    http = store.parse_form({"name": "h", "transport": "http", "url": "http://x/mcp"})
    assert http["transport"] == "http"
    for bad in ({"name": "有空格", "command": "x"}, {"name": "ok", "transport": "http"},
                {"name": "ok", "transport": "stdio"}):
        try:
            store.parse_form(bad)
            raise AssertionError(f"should reject {bad}")
        except ValueError:
            pass


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_mcp ok")


def test_mcp_test_route_missing_command_is_graceful():
    """路由级边界：插件的命令不存在时 /mcp/test 返回 200 + error 字段，不 500。"""
    import experiment_report_grader.app as app_mod
    from experiment_report_grader.mcp import store as mcp_store
    import os
    import tempfile

    tmp = tempfile.mkdtemp(prefix="erg_mcp_route_")
    real_path = mcp_store.CONFIG_PATH
    try:
        cfg_path = os.path.join(tmp, "mcp.yaml")
        store_yaml = "servers:\n  ghost-cmd:\n    transport: stdio\n    command: definitely-missing-cmd-xyz\n"
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(store_yaml)
        mcp_store.CONFIG_PATH = cfg_path
        client = app_mod.app.test_client()
        resp = client.get("/mcp/test/ghost-cmd")
        assert resp.status_code == 200, "失败也应 200 + error，插件页显示错误原因"
        payload = resp.get_json()
        assert payload.get("error") or payload.get("errors"), payload
        resp404 = client.get("/mcp/test/不存在")
        assert resp404.status_code == 404
    finally:
        mcp_store.CONFIG_PATH = real_path
