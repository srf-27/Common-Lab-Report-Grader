"""用户团走查（2026-10-26）修复的回归：分批上传、解析失败可见、权重校验、花名册列名、
长文件名、输出上限、删除课程。"""
import io
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import experiment_report_grader.app as app_mod
import experiment_report_grader.web.state as state_mod
from experiment_report_grader.nodes import rubric_io

# 不替换工厂：走 config.yaml 的真模型（deepseek-flash）。本文件只验上传/花名册/权重/删除，
# 报告是本地可解析的 docx，提取不打模型；即便触发也是真调用。
from experiment_report_grader.app import app  # noqa: E402
from experiment_report_grader.web.state import state  # noqa: E402

TEXT_A = "# 报告甲\n\n## 实验数据\n用逐差法处理 8 组读数，给出不确定度。\n"
TEXT_B = "# 报告乙\n\n## 数据处理\n光杠杆法测微小伸长量，计算杨氏模量。\n"


def _docx(text):
    from docx import Document
    doc = Document()
    for block in text.split("\n\n"):
        doc.add_paragraph(block.replace("\n", " "))
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def _wait(predicate, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    raise AssertionError("等待超时")


def _process(client):
    client.post("/process_reports")
    _wait(lambda: (state.get("task") or {}).get("status") in ("done", "error"))
    return state["task"]


def test_panel_findings_regressions():
    tmp = tempfile.mkdtemp(prefix="erg_panel_")
    real_output, real_sessions = state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR
    real_config = app_mod.CONFIG_PATH
    try:
        state_mod.OUTPUT_FOLDER = tmp
        state_mod.SESSIONS_DIR = str(Path(tmp) / "sessions")
        Path(state_mod.SESSIONS_DIR).mkdir(parents=True)
        app_mod.CONFIG_PATH = os.path.join(tmp, "config.yaml")
        sid = state_mod.new_session("走查课")["id"]
        other = state_mod.new_session("另一门课")["id"]
        state_mod.hydrate_session(sid)
        client = app.test_client()
        # B1：提取报告前必须先有细则；本文件不测细则生成，直接注入最小细则
        state["rubric_json"] = {"criteria": [{"name": "维度甲", "weight": 100, "levels": {}}]}

        # BUG-001 分批上传：第二批不清掉第一批；同名再传只覆盖自己
        assert client.post("/upload_reports", data={"report_files": [
            (_docx(TEXT_A), "甲_20230001.docx"), (_docx(TEXT_B), "乙_20230002.docx")]},
            content_type="multipart/form-data").status_code == 200
        assert _process(client)["status"] == "done"
        assert len(state["extracted_reports"]) == 2, state["extracted_reports"]
        client.post("/upload_reports", data={"report_files": [(_docx(TEXT_A + "\n补充一组对照。"),
                                                              "丙_20230003.docx")]},
                    content_type="multipart/form-data")
        assert _process(client)["status"] == "done"
        names = sorted(r["meta"]["filename"] for r in state["extracted_reports"])
        assert names == ["丙_20230003.docx", "乙_20230002.docx", "甲_20230001.docx"], names
        client.post("/upload_reports", data={"report_files": [(_docx(TEXT_A), "甲_20230001.docx")]},
                    content_type="multipart/form-data")
        assert _process(client)["status"] == "done"
        assert len(state["extracted_reports"]) == 3, "重复上传同一份不应把列表清零"

        # BUG-003 解析失败要能看见，且不能声称成功
        task = _process_after_upload(client, b"not a real docx", "坏文件.docx")
        assert task["status"] == "error" and "失败 1 份" in task["detail"], task
        payload = client.get("/api/reports").get_json()
        assert [f["filename"] for f in payload["failures"]] == ["坏文件.docx"], payload["failures"]
        assert len(payload["reports"]) == 3, "解析失败不应动到已提取的报告"

        # BUG-002 / BUG-011 权重与 JSON 形状
        assert client.post("/rubric_table_save", json={
            "criteria": [{"name": "维度", "weight": -25}]}).status_code == 400
        assert client.post("/rubric_table_save", json={
            "criteria": [{"name": "维度", "weight": "abc"}]}).status_code == 400
        assert client.post("/rubric_table_save", json={"criteria": {"a": 1}}).status_code == 400
        normalized = rubric_io.normalize_weights([{"name": "甲", "weight": -25},
                                                  {"name": "乙", "weight": 25}])
        assert [c["weight"] for c in normalized] == [0.0, 100.0], normalized

        # BUG-004 花名册用「学生学号/学生姓名」也要能对上
        # 真模型从文件名抽到的身份不确定；本项只验列名映射，固定身份后再比对
        ident = {"甲_20230001.docx": ("20230001", "张三"),
                 "乙_20230002.docx": ("20230002", "李四"),
                 "丙_20230003.docx": ("20230003", "赵六")}
        for r in state["extracted_reports"]:
            fn = r["meta"]["filename"]
            if fn in ident:
                r["meta"]["student"] = {"学号": ident[fn][0], "姓名": ident[fn][1]}
        csv = ("学生学号,学生姓名,班级\n20230001,张三,1班\n20230002,李四,1班\n"
               "20230003,赵六,1班\n20239999,王五,1班\n").encode("utf-8-sig")
        client.post("/roster/upload", data={"roster_file": (io.BytesIO(csv), "roster.csv")},
                    content_type="multipart/form-data")
        roster = client.get("/api/roster").get_json()
        assert roster["fields"] == ["学号", "姓名", "班级"], roster["fields"]
        assert roster["suspicious"] == [], roster["suspicious"]
        assert [row["学生姓名"] for row in roster["missing"]] == ["王五"], roster["missing"]

        # BUG-005 超长文件名截断保存，不再 500
        resp = client.post("/upload_criteria", data={
            "criteria_file": (io.BytesIO("评分标准：误差分析 50 分".encode()), "a" * 300 + ".txt")},
            content_type="multipart/form-data")
        assert resp.status_code == 200, resp.status_code
        assert len(resp.get_json()["filename"]) <= 90

        # BUG-008 输出上限越界直接拒绝
        state["config"]["llm"]["openai"]["max_tokens"] = 16384
        for value in ("0", "-1", "999999999", "abc"):
            assert client.post("/settings", data={"max_tokens": value}).status_code == 400, value
        assert state["config"]["llm"]["openai"]["max_tokens"] == 16384

        # BUG-007 删课程连本地目录一起删
        session_path = Path(state_mod.session_dir())
        assert session_path.exists()
        client.post("/session/switch", data={"session_id": other})
        assert client.post("/session/remove", data={"session_id": sid}).status_code == 302
        assert not session_path.exists(), "删除课程后本地目录应一并删除"
    finally:
        state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR = real_output, real_sessions
        app_mod.CONFIG_PATH = real_config
        state_mod.hydrate_session(state_mod.load_sessions()["current"])
        shutil.rmtree(tmp, ignore_errors=True)


def _process_after_upload(client, data, name):
    client.post("/upload_reports", data={"report_files": [(io.BytesIO(data), name)]},
                content_type="multipart/form-data")
    return _process(client)


if __name__ == "__main__":
    test_panel_findings_regressions()
    print("test_panel_findings ok")
