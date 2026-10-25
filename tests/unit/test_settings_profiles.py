"""模型方案 / 评分并发 / 任务 stage 模式的边界用例。"""
import copy
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import yaml

import experiment_report_grader.app as app_mod
from experiment_report_grader.web import state as state_mod
from experiment_report_grader.web import tasks as task_mod


def _client(tmp):
    real_path, real_cfg = app_mod.CONFIG_PATH, app_mod.state["config"]
    app_mod.CONFIG_PATH = os.path.join(tmp, "config.yaml")
    app_mod.state["config"] = copy.deepcopy(real_cfg)
    llm = app_mod.state["config"].setdefault("llm", {})
    llm["backend"] = "openai"
    llm.setdefault("openai", {})["model"] = "m1"
    llm.pop("profiles", None)
    llm.pop("active_profile", None)
    return app_mod.app.test_client(), real_path, real_cfg


def test_profile_boundaries():
    tmp = tempfile.mkdtemp(prefix="erg_prof_")
    client, real_path, real_cfg = _client(tmp)
    try:
        # 空名 / 超长名 → 400
        assert client.post("/llm/profile/save", json={"name": ""}).status_code == 400
        assert client.post("/llm/profile/save", json={"name": "x" * 41}).status_code == 400
        # 保存 → 落盘
        assert client.post("/llm/profile/save", json={"name": "生产"}).status_code == 200
        saved = yaml.safe_load(open(app_mod.CONFIG_PATH, encoding="utf-8"))
        assert saved["llm"]["profiles"]["生产"]["openai"]["model"] == "m1"
        # 同名再存 → 覆盖
        app_mod.state["config"]["llm"]["openai"]["model"] = "m2"
        client.post("/llm/profile/save", json={"name": "生产"})
        assert app_mod.state["config"]["llm"]["profiles"]["生产"]["openai"]["model"] == "m2"
        # 应用不存在的 → 404
        assert client.post("/llm/profile/apply", json={"name": "没有"}).status_code == 404
        # 改乱当前配置 → 应用方案恢复
        app_mod.state["config"]["llm"]["openai"]["model"] = "临时"
        app_mod.state["config"]["llm"]["backend"] = "ollama"
        assert client.post("/llm/profile/apply", json={"name": "生产"}).status_code == 200
        cfg = app_mod.state["config"]["llm"]
        assert cfg["openai"]["model"] == "m2" and cfg["backend"] == "openai"
        assert cfg["active_profile"] == "生产"
        persisted = yaml.safe_load(open(app_mod.CONFIG_PATH, encoding="utf-8"))
        assert persisted["llm"]["backend"] == "openai", "应用后应立即落盘"
        # /api/settings 暴露方案与当前方案
        payload = client.get("/api/settings").get_json()
        assert any(p["name"] == "生产" and p["model"] == "m2" for p in payload["profiles"])
        assert payload["activeProfile"] == "生产"
        # 删除当前方案 → 只清标记，配置不变
        assert client.post("/llm/profile/delete", json={"name": "生产"}).status_code == 200
        assert app_mod.state["config"]["llm"]["active_profile"] == ""
        assert app_mod.state["config"]["llm"]["openai"]["model"] == "m2"
        assert client.post("/llm/profile/delete", json={"name": "生产"}).status_code == 404
    finally:
        app_mod.CONFIG_PATH, app_mod.state["config"] = real_path, real_cfg


def test_grading_workers_boundaries():
    tmp = tempfile.mkdtemp(prefix="erg_work_")
    client, real_path, real_cfg = _client(tmp)
    saved_env = os.environ.pop("ERG_GRADING_WORKERS", None)
    try:
        # 非整数 → 400
        assert client.post("/settings", data={"grading_workers": "abc"}).status_code == 400
        # 0/9 → clamp 1/8；5 → 5
        for raw, expect in (("0", 1), ("9", 8), ("5", 5)):
            assert client.post("/settings", data={"grading_workers": raw}).status_code == 200
            assert app_mod.state["config"]["grading"]["workers"] == expect
        # _grading_workers：config 优先；缺失回退默认 3；非法值也回退
        app_mod.state["config"]["grading"]["workers"] = 6
        assert app_mod._grading_workers() == 6
        app_mod.state["config"]["grading"].pop("workers")
        assert app_mod._grading_workers() == 3
        app_mod.state["config"]["grading"]["workers"] = "broken"
        assert app_mod._grading_workers() == 3
    finally:
        app_mod.CONFIG_PATH, app_mod.state["config"] = real_path, real_cfg
        if saved_env is not None:
            os.environ["ERG_GRADING_WORKERS"] = saved_env


def test_task_stage_mode_boundaries():
    tmp = tempfile.mkdtemp(prefix="erg_stage_")
    real_output, real_sessions = state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR
    try:
        state_mod.OUTPUT_FOLDER = tmp
        state_mod.SESSIONS_DIR = os.path.join(tmp, "sessions")
        os.makedirs(state_mod.SESSIONS_DIR, exist_ok=True)
        t = task_mod.task_start("criteria", "/app/rubric", mode="stage", sid="s_boundary")
        assert t["mode"] == "stage"
        task_mod.task_finish(t, "done")
        assert t["status"] == "done" and t["progress"] == 0, "stage 模式不伪造 100%"
        b = task_mod.task_start("reports", "/app/reports", sid="s_boundary")
        assert b["mode"] == "bar"
        task_mod.task_finish(b, "done")
        assert b["progress"] == 100, "bar 模式完成后应为 100%"
    finally:
        task_mod.RUNNING_TASKS.pop("s_boundary", None)
        state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR = real_output, real_sessions


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_settings_profiles ok")
