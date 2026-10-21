"""并行评分：多份报告同时跑，结果不能丢。"""
import io
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docx import Document

import experiment_report_grader.app as app_mod
from experiment_report_grader.app import app, state
from experiment_report_grader.web import state as state_mod
from fake_llm import CRITERIA, FakeLLM

REPORTS = {
    "a_20230001.docx": "误差分析：A 类不确定度按贝塞尔公式，B 类按仪器允差。\n\n数据处理：逐差法计算。",
    "b_20230002.docx": "误差分析：只做定性描述。\n\n数据处理：列出原始数据，未计算。",
    "c_20230003.docx": "误差分析：给出两类不确定度但未合成。\n\n数据处理：有计算过程。",
}


class SlowLLM(FakeLLM):
    active = 0
    peak = 0
    lock = threading.Lock()

    def chat(self, messages, temperature=0.3, retries=2):
        with type(self).lock:
            type(self).active += 1
            type(self).peak = max(type(self).peak, type(self).active)
        try:
            time.sleep(0.05)
            return super().chat(messages, temperature, retries)
        finally:
            with type(self).lock:
                type(self).active -= 1


def _docx(text):
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def _wait(predicate, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.1)
    return False


def test_parallel_grading_keeps_all_results():
    tmp = tempfile.mkdtemp(prefix="erg_parallel_")
    real_output, real_sessions = state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR
    real_llm = app_mod.llm
    old_workers = os.environ.get("ERG_GRADING_WORKERS")
    try:
        state_mod.OUTPUT_FOLDER = tmp
        state_mod.SESSIONS_DIR = str(Path(tmp) / "sessions")
        Path(state_mod.SESSIONS_DIR).mkdir(parents=True)
        state_mod.hydrate_session(state_mod.new_session("并行测试")["id"])
        app.config["TESTING"] = True
        state["rubric_json"] = {"criteria": [dict(c) for c in CRITERIA]}
        state["rubric"] = "测试细则"
        SlowLLM.peak = 0
        slow = SlowLLM()
        app_mod.llm = lambda cfg=None: slow
        os.environ["ERG_GRADING_WORKERS"] = "2"
        client = app.test_client()

        files = [(_docx(text), name) for name, text in REPORTS.items()]
        resp = client.post("/upload_reports", data={"report_files": files},
                           content_type="multipart/form-data")
        assert resp.status_code == 200 and resp.get_json()["count"] == 3
        assert client.post("/process_reports").status_code == 302
        assert _wait(lambda: (state.get("task") or {}).get("status") in ("done", "error"))
        assert state["task"]["status"] == "done"
        for index, entry in enumerate(state["extracted_reports"]):
            entry["meta"]["student"] = {"学号": f"2023{index:04d}", "姓名": f"学生{index}"}
        assert client.post("/pilot/confirm").status_code == 200

        resp = client.post("/start_grading", data="&".join("report_ids=" + quote(name) for name in REPORTS),
                           content_type="application/x-www-form-urlencoded")
        assert resp.status_code == 302
        assert _wait(lambda: (state.get("grading_status") or {}).get("phase") in
                     ("done", "error", "cancelled"), 60)
        status = state["grading_status"]
        assert status["phase"] == "done", status
        assert status["done"] == 3 and status["total"] == 3
        assert status["workers"] == 2
        assert len(state["grader"].results) == 3
        assert {r["report_id"] for r in state["grader"].results} == set(REPORTS)
        assert all(r["status"] == "graded" for r in state["grader"].results)
        assert SlowLLM.peak >= 2, "两份以上报告应同时在跑"
    finally:
        app_mod.llm = real_llm
        if old_workers is None:
            os.environ.pop("ERG_GRADING_WORKERS", None)
        else:
            os.environ["ERG_GRADING_WORKERS"] = old_workers
        state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR = real_output, real_sessions
        state_mod.hydrate_session(state_mod.load_sessions()["current"])
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_parallel_grading_keeps_all_results()
    print("parallel grading ok")
