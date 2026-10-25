"""细则变更重置与各上传项删除的集成边界（不打真实模型）。"""
import io
import json
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

import experiment_report_grader.app as app_mod
from experiment_report_grader.mcp import store as mcp_store
from experiment_report_grader.nodes import external_scores, rubric_io
from experiment_report_grader.nodes.grader import Grader
from experiment_report_grader.web import state as state_mod
from experiment_report_grader.web.state import hydrate_session, load_sessions, new_session


class FakeLLM:
    def chat(self, messages, temperature=0.3, retries=2, **kwargs):
        return "{}"


RUBRIC = {"criteria": [
    {"name": "维度甲", "weight": 80, "mechanical": False,
     "levels": {lv: "" for lv in ("A", "B", "C", "D", "E")}, "excluded": False},
    {"name": "课外项", "weight": 20, "mechanical": False, "excluded": True,
     "levels": {lv: "" for lv in ("A", "B", "C", "D", "E")}, "non_report": True},
]}


def _make_report(sessions, sid, name, text="正文：不确定度 0.5。"):
    stem = os.path.splitext(name)[0]
    out_dir = os.path.join(sessions, sid, "reports", stem)
    os.makedirs(out_dir, exist_ok=True)
    with io.open(os.path.join(out_dir, "text.md"), "w", encoding="utf-8") as f:
        f.write(text)
    meta = {"filename": name, "output_dir": out_dir, "student": {"姓名": "学生", "学号": "1"},
            "extract_time": "2026-01-01T00:00:00"}
    with io.open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    upload = os.path.join(sessions, sid, "uploads", name)
    with io.open(upload, "w", encoding="utf-8") as f:
        f.write("原始上传内容")
    return {"status": "ok", "meta": meta, "images": []}


def _setup(tmp, reports=("a.docx", "b.docx")):
    """建课程 + 细则 + 报告 + 评分结果 + 向量 + 终审 + 校准样本，返回 (sid, entries)。"""
    real_output, real_sessions = state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR
    real_mcp = mcp_store.CONFIG_PATH
    state_mod.OUTPUT_FOLDER = tmp
    state_mod.SESSIONS_DIR = os.path.join(tmp, "sessions")
    os.makedirs(state_mod.SESSIONS_DIR, exist_ok=True)
    mcp_store.CONFIG_PATH = os.path.join(tmp, "mcp.yaml")
    sid = new_session("重置测试")["id"]
    hydrate_session(sid)
    state_mod.state["rubric_json"] = json.loads(json.dumps(RUBRIC))
    rubric_io.save_rubric_json(RUBRIC, os.path.join(
        state_mod.SESSIONS_DIR, sid, "rubrics", "rubric_current.json"))
    entries = [_make_report(state_mod.SESSIONS_DIR, sid, name) for name in reports]
    state_mod.state["extracted_reports"] = entries
    grader = Grader(json.loads(json.dumps(RUBRIC)), llm_client=FakeLLM(), config={},
                    output_dir=os.path.join(state_mod.SESSIONS_DIR, sid, "grading"),
                    kb_session_dir=os.path.join(state_mod.SESSIONS_DIR, sid))
    grader.results = [
        {"report_id": name, "status": "graded", "graded_at": time.time(),
         "grading": {"scores": {"维度甲": {"level": "B", "evidence": "e", "reasoning": "r"}},
                     "summary": "s", "flags": [],
                     "subtotals": {"维度甲": 80.0, "total": 80.0}}}
        for name in reports]
    state_mod.state["grader"] = grader
    grader._ensure_kb()
    grader.kb.collection.add(ids=["kb-" + n for n in reports],
                             documents=["正文 " + n for n in reports],
                             metadatas=[{"report_id": n, "scope": sid} for n in reports])
    dim = grader._dimension_collection("维度甲", create=True)
    dim.add(ids=["dim-" + n for n in reports],
            documents=["维度内容 " + n for n in reports],
            metadatas=[{"report_id": n, "dimension": "维度甲", "level": "B"} for n in reports])
    state_mod.state["approved_ids"] = {reports[0]}
    from experiment_report_grader.web.state import save_approved
    save_approved(state_mod.state["approved_ids"])
    state_mod.state["corrections"] = {reports[0]: "请补充"}
    # 校准样本（含模型判级，重置后应作废）
    pilot_dir = os.path.join(state_mod.SESSIONS_DIR, sid, "pilot")
    os.makedirs(os.path.join(pilot_dir, "uploads"), exist_ok=True)
    sample_stem = os.path.join(pilot_dir, "reports", "样本1")
    os.makedirs(sample_stem, exist_ok=True)
    io.open(os.path.join(sample_stem, "text.md"), "w", encoding="utf-8").write("样本正文")
    io.open(os.path.join(pilot_dir, "uploads", "样本1.docx"), "w", encoding="utf-8").write("x")
    with io.open(os.path.join(pilot_dir, "pilot.json"), "w", encoding="utf-8") as f:
        json.dump({"reports": [{"filename": "样本1.docx", "chars": 4,
                                "text": "pilot/reports/样本1/text.md",
                                "ai": {"维度甲": "A"}, "teacher": {"维度甲": "A"},
                                "status": "graded"}],
                   "confirmed_at": 0, "rubric_hash": ""}, f, ensure_ascii=False)
    return sid, entries, grader


def _teardown(real_output, real_sessions, real_mcp):
    state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR = real_output, real_sessions
    mcp_store.CONFIG_PATH = real_mcp
    hydrate_session(load_sessions()["current"])


def _collections(base):
    from experiment_report_grader.embedding import Chroma
    try:
        store = Chroma(config={}, session_dir=base, create=False)
        return {c.name: c.count() for c in store.client.list_collections()}
    except Exception:
        return {}


def test_rubric_save_needs_confirm_then_resets():
    tmp = tempfile.mkdtemp(prefix="erg_reset_")
    real = (state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR, mcp_store.CONFIG_PATH)
    try:
        sid, entries, grader = _setup(tmp)
        base = os.path.join(state_mod.SESSIONS_DIR, sid)
        client = app_mod.app.test_client()
        payload = {"criteria": RUBRIC["criteria"]}

        # 未确认 → 409 needReset，数据不动
        resp = client.post("/rubric_table_save", json=payload)
        assert resp.status_code == 409 and resp.get_json().get("needReset")
        assert state_mod.state["extracted_reports"], "未确认前不得删数据"

        # 确认（force 跳过判据含糊警告）→ 重置
        resp = client.post("/rubric_table_save",
                           json={**payload, "confirm_reset": True, "force": True})
        assert resp.status_code == 200
        state = state_mod.state
        assert state["extracted_reports"] == [] and state["grader"] is None
        assert state["approved_ids"] == set() and state["corrections"] == {}
        assert not os.path.exists(os.path.join(base, "reports"))
        assert not os.path.exists(os.path.join(base, "grading"))
        assert all(count == 0 for count in _collections(base).values()), _collections(base)
        # 上传原件保留
        for entry in entries:
            assert os.path.exists(os.path.join(base, "uploads", entry["meta"]["filename"]))
        # 校准样本：模型判级作废，教师手填保留
        pilot = json.load(io.open(os.path.join(base, "pilot", "pilot.json"), encoding="utf-8"))
        assert pilot["reports"][0]["ai"] == {} and pilot["reports"][0]["status"] == "pending"
        assert pilot["reports"][0]["teacher"] == {"维度甲": "A"}
        # 细则本身已更新
        assert rubric_io.load_rubric_json(os.path.join(base, "rubrics", "rubric_current.json"))
    finally:
        _teardown(*real)
        shutil.rmtree(tmp, ignore_errors=True)


def test_process_criteria_needs_confirm():
    tmp = tempfile.mkdtemp(prefix="erg_pc_")
    real = (state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR, mcp_store.CONFIG_PATH)
    try:
        sid, _, _ = _setup(tmp, reports=("a.docx",))
        client = app_mod.app.test_client()
        resp = client.post("/process_criteria")
        assert resp.status_code == 409 and resp.get_json().get("needReset")
        # 空课程（无下游）不受影响：404/302 之外不应是 409 —— 用新会话验证
        sid2 = new_session("空课程")["id"]
        hydrate_session(sid2)
        resp2 = client.post("/process_criteria")
        assert resp2.status_code != 409
    finally:
        _teardown(*real)
        shutil.rmtree(tmp, ignore_errors=True)


def test_report_delete_purges_everything():
    tmp = tempfile.mkdtemp(prefix="erg_del_")
    real = (state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR, mcp_store.CONFIG_PATH)
    try:
        sid, entries, grader = _setup(tmp)
        base = os.path.join(state_mod.SESSIONS_DIR, sid)
        client = app_mod.app.test_client()
        resp = client.post("/reports/delete/a.docx")
        assert resp.status_code == 200, resp.get_data(as_text=True)
        state = state_mod.state
        assert [e["meta"]["filename"] for e in state["extracted_reports"]] == ["b.docx"]
        assert [r["report_id"] for r in state["grader"].results] == ["b.docx"]
        assert "a.docx" not in state["approved_ids"] and state["corrections"] == {}
        assert not os.path.exists(os.path.join(base, "reports", "a"))
        assert not os.path.exists(os.path.join(base, "uploads", "a.docx"))
        assert os.path.exists(os.path.join(base, "uploads", "b.docx"))
        # 向量：a 的记录消失，b 保留
        remaining = state["grader"].kb.collection.get(where={"report_id": "a.docx"}, include=[])
        assert not (remaining.get("ids") or [])
        remaining_b = state["grader"].kb.collection.get(where={"report_id": "b.docx"}, include=[])
        assert remaining_b.get("ids") == ["kb-b.docx"]
        # 边界：不存在 404；运行中 409
        assert client.post("/reports/delete/a.docx").status_code == 404
        state["grading_status"] = {"phase": "running"}
        assert client.post("/reports/delete/b.docx").status_code == 409
        state["grading_status"] = None
    finally:
        _teardown(*real)
        shutil.rmtree(tmp, ignore_errors=True)


def test_pilot_and_criteria_and_external_cleanup():
    tmp = tempfile.mkdtemp(prefix="erg_clean_")
    real = (state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR, mcp_store.CONFIG_PATH)
    try:
        sid, _, _ = _setup(tmp, reports=("a.docx",))
        base = os.path.join(state_mod.SESSIONS_DIR, sid)
        client = app_mod.app.test_client()

        # pilot 删除
        assert client.post("/pilot/delete", json={"filename": "样本1.docx"}).status_code == 200
        pilot = app_mod._load_pilot(base)
        assert pilot["reports"] == []
        assert not os.path.exists(os.path.join(base, "pilot", "reports", "样本1"))
        assert not os.path.exists(os.path.join(base, "pilot", "uploads", "样本1.docx"))
        assert client.post("/pilot/delete", json={"filename": "样本1.docx"}).status_code == 404

        # 细则上传文件清除
        updir = os.path.join(base, "uploads")
        io.open(os.path.join(updir, "criteria_old.txt"), "w", encoding="utf-8").write("x")
        io.open(os.path.join(updir, "experiment_old.pdf"), "w", encoding="utf-8").write("x")
        resp = client.post("/criteria/clear")
        assert resp.get_json()["removed"] == 2
        assert os.path.exists(os.path.join(updir, "a.docx")), "报告原件不受影响"
        assert "criteria_upload" not in state_mod.state

        # 成绩单导入 → 清除回滚
        scores = {"课外项": {"1": 88}}
        external_scores.save(base, {"file": "s.xlsx", "at": 1, "scores": scores, "raw": {}})
        state_mod.state["external"] = {"file": "s.xlsx", "scores": scores}
        grader = state_mod.state["grader"]
        students = {"a.docx": {"学号": "1"}}
        external_scores.apply_to_results(grader.results, state_mod.state["rubric_json"],
                                         state_mod.state["external"], lambda k: students.get(k))
        before = grader.results[0]["grading"]["scores"]["课外项"]["external"]
        assert before is True and grader.results[0]["grading"]["subtotals"]["total"] > 80
        resp = client.post("/external/clear")
        assert resp.get_json()["cleared"] == 1
        assert "课外项" not in grader.results[0]["grading"]["scores"]
        assert grader.results[0]["grading"]["subtotals"]["total"] == 64.0, \
            "小计应回滚为维度甲 B(80 分)×80% 权重"
        assert not storage_exists(os.path.join(base, "external_scores.json"))
        assert state_mod.state["external"] == {}
        # 再次清除是 no-op
        assert client.post("/external/clear").get_json()["cleared"] == 0
    finally:
        _teardown(*real)
        shutil.rmtree(tmp, ignore_errors=True)


def storage_exists(path):
    from experiment_report_grader import storage
    return storage.exists(path)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_reset_and_delete ok")
