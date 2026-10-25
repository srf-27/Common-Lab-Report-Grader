"""课程会话与全局运行状态：目录、索引、审批记录、MCP 挂载、会话补水。"""

import os
import re
import threading
import time

from .. import storage
from ..nodes import rubric_io
from ..nodes import external_scores
from .usage import load as load_usage
from ..nodes.grader import Grader
from ..factory import llm
from ..utils.llm_client import load_config

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
OUTPUT_FOLDER = os.path.join(PROJECT_ROOT, "data", "output")
SESSIONS_DIR = os.path.join(OUTPUT_FOLDER, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

VALID_LEVELS = ("A", "B", "C", "D", "E")
STUDENT_FIELDS = ["班级", "学院", "学号", "姓名"]
SUBDIRS = ("rubrics", "reports", "grading", "uploads")

# 会话隔离的运行态注册表：sid -> 进度 dict。后台线程只更新自己持有的 dict 引用；
# hydrate 按当前会话恢复，切课后旧线程的写入不会漏进新会话。
RUNNING_STATUS = {}

state = {
    "config": load_config(),
    "session": None,
    "rubric": None,
    "rubric_json": None,
    "criteria_doc": "",
    "experiment_doc": "",
    "external": {},
    "extracted_reports": [],
    "report_uploads": [],
    "grader": None,
    "corrections": {},
    "calibration": None,
    "grading_status": None,
    "grading_lock": threading.Lock(),
    "task": None,
    "approved_ids": set(),
    "mcp": {"servers": [], "resources": [], "search_tool": "", "prompt": "", "max_chars": 4000},
    "mcp_status": [],
    "flow": {},
    "usage": {"cost": 0.0, "tokens_in": 0, "tokens_out": 0, "calls": 0, "model": "", "seq": 0},
}


def sanitize_filename(name):
    name = os.path.basename(str(name or "")).strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(". ")
    return name or "unnamed"


def _read_json(path, default):
    return storage.read_json(path, default)


def _write_json(path, data, indent=None):
    storage.write_json(path, data, indent=indent)


def sessions_index_path():
    return os.path.join(OUTPUT_FOLDER, "sessions.json")


def load_sessions():
    idx = _read_json(sessions_index_path(), {"sessions": [], "current": None})
    seen, unique = set(), []
    for entry in idx.get("sessions") or []:
        if entry.get("id") and entry["id"] not in seen:
            seen.add(entry["id"])
            unique.append(entry)
    idx["sessions"] = unique
    if idx.get("current") not in seen:
        idx["current"] = unique[-1]["id"] if unique else None
    return idx


def save_sessions(idx):
    _write_json(sessions_index_path(), idx, indent=2)


def session_dir(sid=None):
    return os.path.join(SESSIONS_DIR, sid or state["session"])


def session_sub(sub):
    d = os.path.join(session_dir(), sub)
    os.makedirs(d, exist_ok=True)
    return d


def approved_path():
    return os.path.join(session_dir(), "approved.json")


def load_approved():
    return set(_read_json(approved_path(), []))


def save_approved(ids):
    _write_json(approved_path(), sorted(ids))


def new_session(name):
    idx = load_sessions()
    base = "s_" + time.strftime("%Y%m%d_%H%M%S")
    sid, n = base, 1
    taken = {s["id"] for s in idx["sessions"]}
    while sid in taken or os.path.exists(os.path.join(SESSIONS_DIR, sid)):
        n += 1
        sid = f"{base}_{n}"
    entry = {"id": sid, "name": (name or "").strip() or f"课程 {len(idx['sessions']) + 1}"}
    idx["sessions"].append(entry)
    idx["current"] = sid
    save_sessions(idx)
    for sub in SUBDIRS:
        os.makedirs(os.path.join(SESSIONS_DIR, sid, sub), exist_ok=True)
    return entry


def remove_session(sid):
    idx = load_sessions()
    idx["sessions"] = [s for s in idx["sessions"] if s["id"] != sid]
    if not idx["sessions"]:
        save_sessions(idx)
        return new_session("默认课程")
    if idx["current"] == sid:
        idx["current"] = idx["sessions"][-1]["id"]
    save_sessions(idx)
    return next(s for s in idx["sessions"] if s["id"] == idx["current"])


def _images_of(report_dir):
    """从 images/ 目录还原图片记录（meta.json 不存图片列表）。"""
    img_dir = os.path.join(report_dir, "images")
    if not os.path.isdir(img_dir):
        return []
    images = []
    for name in sorted(os.listdir(img_dir)):
        page = re.match(r"fig_(\d{3})_", name)
        images.append({"filename": name, "page": int(page.group(1)) if page else "",
                       "context": ""})
    return images


def hydrate_session(sid):
    """切换/恢复课程：清空内存状态并按会话目录重建（含已评结果与 MCP 挂载）。"""
    from . import tasks as task_mod  # 函数内导入，避免与 tasks -> state 的模块级互引

    state["session"] = sid
    # 易失记忆从存储恢复：教师重评意见、上一轮任务/评分的终态、校准工作区
    state["corrections"] = storage.read_json(
        os.path.join(session_dir(sid), "corrections.json"), {}) or {}
    state["extracted_reports"] = []
    state["report_uploads"] = []
    state["grader"] = None
    state["rubric"] = None
    state["rubric_json"] = None
    state["criteria_doc"] = ""
    state["experiment_doc"] = ""
    state["external"] = {}
    state["calibration"] = None
    # 易跨会话残留的 key 一并复位：进度从注册表恢复本会话的，其余清空
    state["grading_status"] = RUNNING_STATUS.get(sid)
    state["task"] = task_mod.RUNNING_TASKS.get(sid)
    # 无在跑任务时恢复上一轮终态快照（重启后线程已死，running 不复活）
    if state["grading_status"] is None:
        snapshot = storage.read_json(
            os.path.join(session_dir(sid), "memory", "grading_status.json"), None)
        if snapshot and snapshot.get("phase") in ("done", "cancelled", "error"):
            state["grading_status"] = snapshot
    if state["task"] is None:
        snapshot = storage.read_json(os.path.join(session_dir(sid), "memory", "task.json"), None)
        if snapshot and snapshot.get("status") in ("done", "error", "cancelled"):
            state["task"] = snapshot
    calib = storage.read_json(os.path.join(session_dir(sid), "calibration_workspace.json"), None)
    if isinstance(calib, dict) and calib.get("text"):
        state["calibration"] = calib
    state["rubric_warnings"] = None
    state["mcp_status"] = []
    state.pop("mcp_refs", None)
    state.pop("criteria_upload", None)
    state.pop("criteria_experiment", None)
    state["usage"] = load_usage(session_dir(sid))
    for sub in SUBDIRS:
        os.makedirs(os.path.join(SESSIONS_DIR, sid, sub), exist_ok=True)

    rubric_json = rubric_io.load_rubric_json(
        os.path.join(session_dir(sid), "rubrics", "rubric_current.json"))
    if rubric_json and rubric_json.get("criteria"):
        state["rubric_json"] = rubric_json
        state["rubric"] = rubric_io.criteria_to_markdown(rubric_json)
        markdown_path = os.path.join(session_dir(sid), "rubrics", "rubric_latest.md")
        if not storage.exists(markdown_path):
            storage.write_text(markdown_path, state["rubric"])
    state["criteria_doc"] = storage.read_text(
        os.path.join(session_dir(sid), "rubrics", "criteria_doc.txt"))
    state["experiment_doc"] = storage.read_text(
        os.path.join(session_dir(sid), "rubrics", "experiment_doc.txt"))

    reports_dir = os.path.join(session_dir(sid), "reports")
    for name in sorted(os.listdir(reports_dir)):
        meta = _read_json(os.path.join(reports_dir, name, "meta.json"), None)
        if meta:
            state["extracted_reports"].append(
                {"status": "ok", "meta": meta, "images": _images_of(os.path.join(reports_dir, name))})

    results_path = os.path.join(session_dir(sid), "grading", "grading_results.json")
    results = _read_json(results_path, []) if state["rubric_json"] else []
    if results:
        grader = Grader(state["rubric_json"], llm_client=llm(state["config"]),
                        config=state["config"], output_dir=os.path.join(session_dir(sid), "grading"),
                        similarity_scope=sid, kb_session_dir=session_dir(sid))
        grader.results = results
        state["grader"] = grader

    external = external_scores.load(session_dir(sid))
    if external and state["rubric_json"] and state["grader"]:
        students = {r["meta"]["filename"]: (r["meta"].get("student") or {})
                    for r in state["extracted_reports"]}
        external_scores.apply_to_results(state["grader"].results, state["rubric_json"],
                                         external, students.get)
    state["external"] = external

    state["approved_ids"] = load_approved()
    state["mcp"] = load_mcp_mount(sid)
    state["flow"] = storage.read_json(os.path.join(session_dir(sid), "flow.json"), {}) or {}


def mcp_mount_path(sid=None):
    return os.path.join(session_dir(sid), "mcp.json")


def load_mcp_mount(sid=None):
    data = _read_json(mcp_mount_path(sid), {})
    return {"servers": data.get("servers") or [], "resources": data.get("resources") or [],
            "search_tool": data.get("search_tool") or "", "prompt": data.get("prompt") or "",
            "max_chars": int(data.get("max_chars") or 4000)}


def save_mcp_mount(mount, sid=None):
    _write_json(mcp_mount_path(sid), mount, indent=2)
    state["mcp"] = mount


def roster_path():
    return os.path.join(session_dir(), "roster.json")


def load_roster():
    roster = _read_json(roster_path(), None)
    if not roster or not roster.get("headers"):
        return None
    return roster


def save_roster(roster):
    _write_json(roster_path(), roster, indent=2)
