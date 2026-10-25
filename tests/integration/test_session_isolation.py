"""会话隔离回归：评分运行中切换课程，旧会话任务不得污染新会话的任何状态。

用假 _grade_one（不调 LLM，带延迟保证切课发生在运行中）驱动 start_grading，
断言 C1/C2/C5 类缺陷已修复：进度、报告列表、细则、教师意见互不串扰。
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

import experiment_report_grader.app as app_mod                      # noqa: E402
from experiment_report_grader.web import state as state_mod         # noqa: E402
from experiment_report_grader.web.state import hydrate_session, new_session, save_sessions, load_sessions  # noqa: E402


def _make_report(sessions, sid, name, text):
    out_dir = os.path.join(sessions, sid, "reports", name)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "text.md"), "w", encoding="utf-8") as f:
        f.write(text)
    meta = {"filename": name, "output_dir": out_dir, "student": {},
            "extract_time": "2026-01-01T00:00:00"}
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    return {"status": "ok", "meta": meta, "images": []}


def test_switch_session_mid_grading_is_isolated():
    tmp = tempfile.mkdtemp(prefix="erg_iso_")
    real_output, real_sessions = state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR
    real_grade_one = app_mod._grade_one
    try:
        state_mod.OUTPUT_FOLDER = os.path.join(tmp, "output")
        state_mod.SESSIONS_DIR = os.path.join(state_mod.OUTPUT_FOLDER, "sessions")
        os.makedirs(state_mod.SESSIONS_DIR, exist_ok=True)

        # 会话 A：细则 + 已确认校准 + 一份报告
        entry_a = new_session("课程A")
        sid_a = entry_a["id"]
        hydrate_session(sid_a)
        rubric_a = {"criteria": [{"name": "维度甲", "weight": 100.0,
                                  "levels": {lv: "" for lv in ("A", "B", "C", "D", "E")}}]}
        state_mod.state["rubric_json"] = rubric_a
        app_mod._save_rubric(rubric_a, "标准A", "")
        app_mod._save_pilot({"reports": [], "confirmed_at": time.time(),
                             "rubric_hash": app_mod._rubric_hash()})
        report_a = _make_report(state_mod.SESSIONS_DIR, sid_a, "r1.md", "课程A的报告正文")
        state_mod.state["extracted_reports"] = [report_a]

        # 会话 B：不同的细则，无报告
        entry_b = new_session("课程B")
        sid_b = entry_b["id"]
        hydrate_session(sid_b)
        rubric_b = {"criteria": [{"name": "维度乙", "weight": 100.0,
                                  "levels": {lv: "" for lv in ("A", "B", "C", "D", "E")}}]}
        state_mod.state["rubric_json"] = rubric_b
        app_mod._save_rubric(rubric_b, "标准B", "")

        # 回到 A，启动评分；假 _grade_one 慢到足以中途切走
        idx = load_sessions()
        idx["current"] = sid_a
        save_sessions(idx)
        hydrate_session(sid_a)
        state_mod.state["extracted_reports"] = [report_a]
        # hydrate 会从存储恢复教师意见；此处模拟用户刚提交了重评意见
        state_mod.state["corrections"]["r1.md"] = "课程A的教师意见"

        calls = []

        def fake_grade_one(grader, entry, references="", corrections=None):
            corrections = corrections if corrections is not None else {}
            calls.append((entry["meta"]["filename"], corrections.get(entry["meta"]["filename"],
                                                                     "<无意见>")))
            time.sleep(0.4)
            return None

        app_mod._grade_one = fake_grade_one
        client = app_mod.app.test_client()
        resp = client.post("/start_grading", data={"report_ids": "r1.md"},
                           headers={"Accept": "application/json"})
        assert resp.get_json()["ok"], resp.get_data(as_text=True)
        assert (state_mod.state.get("grading_status") or {}).get("phase") == "running"
        sid_at_start = state_mod.state["session"]

        # 评分运行中切到课程 B
        hydrate_session(sid_b)
        assert state_mod.state["session"] == sid_b
        grading_status_b = state_mod.state.get("grading_status")
        assert not (grading_status_b or {}).get("phase") == "running", \
            "切课后新课不应看到旧课的运行中状态"

        # 等旧会话评分线程结束
        deadline = time.time() + 10
        while time.time() < deadline:
            status_a = state_mod.RUNNING_STATUS.get(sid_a) or {}
            if status_a.get("phase") in ("done", "cancelled", "error"):
                break
            time.sleep(0.05)
        assert (state_mod.RUNNING_STATUS.get(sid_a) or {}).get("phase") == "done", \
            f"旧会话评分应正常完成，实际 {state_mod.RUNNING_STATUS.get(sid_a)}"

        # 旧会话完成后，B 的内存状态不被覆盖
        assert state_mod.state["session"] == sid_b
        assert state_mod.state.get("grading_status") in (grading_status_b, None), \
            "旧会话的完成状态不得写入新会话"
        assert state_mod.state["rubric_json"]["criteria"][0]["name"] == "维度乙"
        assert state_mod.state["extracted_reports"] == []
        assert state_mod.state["corrections"] == {}, "旧会话不得动新会话的教师意见"

        # 旧会话的结果落在旧会话目录（grading_results.json），新课目录没有
        results_a = os.path.join(state_mod.SESSIONS_DIR, sid_a, "grading", "grading_results.json")
        results_b = os.path.join(state_mod.SESSIONS_DIR, sid_b, "grading", "grading_results.json")
        assert os.path.exists(results_a), "评分结果应写入旧会话目录"
        assert not os.path.exists(results_b), "评分结果不得写入新会话目录"

        # 假评分确实消费了 A 的教师意见（corrections 捕获传入）
        assert calls and calls[0][0] == "r1.md"
        assert calls[0][1] == "课程A的教师意见"
        assert sid_at_start == sid_a
    finally:
        app_mod._grade_one = real_grade_one
        state_mod.RUNNING_STATUS.clear()
        state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR = real_output, real_sessions
        hydrate_session(load_sessions()["current"])
        shutil.rmtree(tmp, ignore_errors=True)


def test_corrections_survive_regrade_failure():
    """llm_failed 时教师意见不被清空（保留供下次重评）。"""
    corrections = {"r1.md": "请补充误差分析"}
    grader = type("G", (), {"results": [], "rubric": {"criteria": []}})()
    entry = {"meta": {"filename": "r1.md", "output_dir": "x"},
             "images": [], "status": "ok"}
    saved = (app_mod._report_text, app_mod._image_entries,
             app_mod._image_descriptions, app_mod._grading_workers)
    try:
        app_mod._report_text = lambda e: "正文"
        app_mod._image_entries = lambda e: []
        app_mod._image_descriptions = lambda e: ""
        app_mod._grading_workers = lambda: 1
        grader.assign_items = lambda items, shots_query="": {}
        grader.grade_single = lambda *a, **k: {"result": {"report_id": "r1.md",
                                                          "status": "llm_failed",
                                                          "graded_at": 1}, "needs_review": True}
        outcome = app_mod._grade_one(grader, entry, references="", corrections=corrections)
        assert outcome["result"]["status"] == "llm_failed"
        assert corrections.get("r1.md") == "请补充误差分析", "评分失败时教师意见必须保留"
    finally:
        (app_mod._report_text, app_mod._image_entries,
         app_mod._image_descriptions, app_mod._grading_workers) = saved


if __name__ == "__main__":
    test_switch_session_mid_grading_is_isolated()
    test_corrections_survive_regrade_failure()
    print("test_session_isolation ok")
