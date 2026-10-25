"""技能包加载器：skills/<名字>/skill.py 提供 TOOLS_SCHEMA + dispatch(name, args)。

与 utils/calc_tools 同契约；SKILL.md 首段作为描述。按路径 + mtime 缓存模块。
"""

import importlib.util
import os
import threading

SKILLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "skills")

_LOCK = threading.Lock()
_CACHE = {}


def _meta(name):
    path = os.path.join(SKILLS_DIR, name, "skill.py")
    doc = ""
    md = os.path.join(SKILLS_DIR, name, "SKILL.md")
    if os.path.exists(md):
        with open(md, "r", encoding="utf-8") as f:
            doc = next((line.strip("# \t") for line in f if line.strip()), "")
    return path, doc


def list_skills():
    """扫描 skills/ 目录：[{name, desc, tools}]。"""
    out = []
    if not os.path.isdir(SKILLS_DIR):
        return out
    for name in sorted(os.listdir(SKILLS_DIR)):
        path, desc = _meta(name)
        if not os.path.exists(path):
            continue
        module = load(name)
        tools = [t["function"]["name"] for t in (getattr(module, "TOOLS_SCHEMA", None) or [])]
        if tools:
            out.append({"name": name, "desc": desc, "tools": tools})
    return out


def load(name):
    path, _ = _meta(name)
    if not os.path.exists(path):
        return None
    mtime = os.path.getmtime(path)
    with _LOCK:
        hit = _CACHE.get(name)
        if hit and hit[0] == mtime:
            return hit[1]
    spec = importlib.util.spec_from_file_location(f"erg_skill_{name}", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    if not hasattr(module, "TOOLS_SCHEMA") or not hasattr(module, "dispatch"):
        return None
    with _LOCK:
        _CACHE[name] = (mtime, module)
    return module
