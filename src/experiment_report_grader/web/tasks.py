"""后台任务（上传处理、批量评分）的进度状态：按会话登记，线程持引用更新。

线程绝不在写时刻读 state["task"]——切课后旧线程的进度更新只会落在自己持有的
task dict 上（登记在 RUNNING_TASKS[sid]），新会话不受影响。
"""

import os
import threading
import time

from .. import storage

task_lock = threading.Lock()
RUNNING_TASKS = {}  # sid -> task dict


def _snapshot(sid, t):
    if sid:
        try:
            from .state import session_dir
            data = {k: v for k, v in t.items() if k != "thinking"}
            storage.write_json(os.path.join(session_dir(sid), "memory", "task.json"), data)
        except Exception:
            pass


def task_start(kind, redirect, total=0, sid=None, mode="bar"):
    """创建并登记任务进度，返回 task dict；后台线程应持该引用调用 task_update/task_finish。

    mode="bar"：确定性进度（逐文件/逐份），前端渲染进度条；
    mode="stage"：无法如实量化进度的长任务（如单次长 LLM 调用），前端渲染阶段 + 已运行时长。
    """
    from .state import state

    sid = sid or state.get("session")
    t = {"kind": kind, "status": "running", "progress": 0, "stage": "准备中",
         "detail": "", "cancel": False, "redirect": redirect, "error": "",
         "done": 0, "total": total, "started": time.time(), "sid": sid, "mode": mode}
    with task_lock:
        if sid:
            RUNNING_TASKS[sid] = t
        if sid == state.get("session"):
            state["task"] = t
    _snapshot(sid, t)
    return t


def task_update(t, progress=None, stage=None, detail=None, done=None, total=None, thinking=None):
    if not t:
        return
    with task_lock:
        if progress is not None:
            t["progress"] = int(progress)
        if stage is not None:
            t["stage"] = stage
        if detail is not None:
            t["detail"] = detail
        if done is not None:
            t["done"] = done
        if total is not None:
            t["total"] = total
        if thinking:
            t["thinking"] = ((t.get("thinking") or "") + thinking)[-600:]


def task_cancelled(t):
    return bool(t and t.get("cancel"))


def task_finish(t, status, error=""):
    if not t:
        return
    with task_lock:
        t["status"] = status
        t["error"] = str(error)
        t["ended"] = time.time()
        if status == "done" and t.get("mode") != "stage":
            t["progress"] = 100  # stage 模式没有真实百分比，不伪造 100%
    _snapshot(t.get("sid"), t)


def task_running(t=None):
    """无参查当前会话；传 task dict 查指定任务。"""
    if t is not None:
        return bool(t.get("status") == "running")
    from .state import state

    t = state.get("task")
    return bool(t and t.get("status") == "running")
