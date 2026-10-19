"""后台任务（上传处理、批量评分）的进度状态。"""

import threading
import time

from .state import state

task_lock = threading.Lock()


def task_start(kind, redirect, total=0):
    with task_lock:
        state["task"] = {"kind": kind, "status": "running", "progress": 0, "stage": "准备中",
                         "detail": "", "cancel": False, "redirect": redirect, "error": "",
                         "done": 0, "total": total, "started": time.time()}


def task_update(progress=None, stage=None, detail=None, done=None, total=None):
    t = state.get("task")
    if not t:
        return
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


def task_cancelled():
    t = state.get("task")
    return bool(t and t.get("cancel"))


def task_finish(status, error=""):
    t = state.get("task")
    if not t:
        return
    t["status"] = status
    t["error"] = str(error)
    t["ended"] = time.time()
    if status == "done":
        t["progress"] = 100


def task_running():
    t = state.get("task")
    return bool(t and t["status"] == "running")
