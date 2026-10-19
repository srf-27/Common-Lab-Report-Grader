"""查询供应商账户余额，并用余额差校准估算成本。

余额接口各厂商不同，这里按 Base URL 逐个探测；查到的余额按账号（Base URL + Key 尾部）
存到 data/output/balance.json，保留最近 200 次快照。余额差只用来校验/校准，不改历史记录。
"""

import hashlib
import json
import os
import threading
import time

import requests

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "output")
PATH = os.path.join(OUTPUT_DIR, "balance.json")
CACHE_SECONDS = 15
MAX_HISTORY = 200

_LOCK = threading.Lock()
_CACHE = {"at": 0.0, "key": "", "value": None}

# (路径, 解析函数)：按顺序试，第一个成功的算数
ADAPTERS = (
    ("/user/balance", lambda data: (
        (data.get("balance_infos") or [{}])[0].get("total_balance"),
        (data.get("balance_infos") or [{}])[0].get("currency"),
    )),
    ("/v1/user/info", lambda data: ((data.get("data") or {}).get("balance"), "CNY")),
    ("/v1/users/me/balance", lambda data: (
        (data.get("data") or {}).get("available_balance"), "CNY")),
)


def _account_key(base_url, api_key):
    tail = (api_key or "")[-6:]
    return hashlib.sha1(f"{base_url}|{tail}".encode("utf-8")).hexdigest()[:12]


def _read():
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(data):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PATH)


def query(cfg, force=False):
    """查一次余额；15 秒内重复请求走缓存。失败不抛异常，回 {ok: False, error}。"""
    llm = cfg.get("llm") or {}
    if llm.get("backend") != "openai":
        return {"ok": False, "error": "余额查询只支持 OpenAI 兼容接口（当前是其他协议）"}
    conf = llm.get("openai") or {}
    base = (conf.get("base_url") or "").rstrip("/")
    if not base:
        return {"ok": False, "error": "还没配置 Base URL"}
    api_key = os.environ.get(conf.get("api_key") or "", conf.get("api_key") or "")
    if not api_key:
        return {"ok": False, "error": "还没有可用的 API Key"}

    cache_key = f"{base}|{api_key[-6:]}"
    if not force and _CACHE["value"] and _CACHE["key"] == cache_key \
            and time.time() - _CACHE["at"] < CACHE_SECONDS:
        return _CACHE["value"]

    last_error = ""
    for path, parse in ADAPTERS:
        url = base + path
        try:
            resp = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=8)
        except requests.RequestException as exc:
            last_error = f"连不上 {base}：{str(exc)[:120]}"
            continue
        if resp.status_code in (401, 403):
            last_error = "API Key 无效，或该 Key 没有查询余额的权限"
            continue
        if resp.status_code == 404:
            last_error = "该服务没有余额接口"
            continue
        if resp.status_code != 200:
            last_error = f"{path} 返回 {resp.status_code}"
            continue
        try:
            data = resp.json()
        except ValueError:
            last_error = f"{path} 返回的不是 JSON"
            continue
        try:
            total, currency = parse(data)
        except (AttributeError, IndexError, TypeError):
            total, currency = None, None
        try:
            amount = float(total)
        except (TypeError, ValueError):
            last_error = f"{path} 里没有余额字段"
            continue
        value = {
            "ok": True, "total": round(amount, 4), "currency": (currency or "CNY").upper(),
            "source": path, "at": int(time.time()),
        }
        _CACHE.update({"at": time.time(), "key": cache_key, "value": value})
        return value

    value = {"ok": False, "error": last_error or "没有找到可用的余额接口"}
    _CACHE.update({"at": time.time(), "key": cache_key, "value": value})
    return value


def reset():
    """把基线重置为「下次查询到的余额」（充值或换账号后调用）。"""
    state = _read()
    state["first"] = None
    state["last"] = None
    with _LOCK:
        _write(state)


def refresh(cfg, events=(), force=True):
    """查询余额并落盘快照；再用「首次余额 − 当前余额」校正估算成本。"""
    conf = (cfg.get("llm") or {}).get("openai") or {}
    base = (conf.get("base_url") or "").rstrip("/")
    api_key = os.environ.get(conf.get("api_key") or "", conf.get("api_key") or "")
    account = _account_key(base, api_key)

    state = _read()
    if state.get("account") != account:
        state = {"account": account, "first": None, "last": None, "history": []}

    result = query(cfg, force=force)
    if result.get("ok"):
        now = {"t": result["at"], "total": result["total"], "currency": result["currency"]}
        with _LOCK:
            state["last"] = now
            state["first"] = state.get("first") or now
            state["history"] = (state.get("history") or [])[-(MAX_HISTORY - 1):] + [now]
            _write(state)
    elif not state.get("last"):
        return {**result, "account": account}

    first = state.get("first")
    last = state.get("last")
    spent = None
    if first and last and last["total"] <= first["total"]:
        spent = round(first["total"] - last["total"], 4)

    since = (first or {}).get("t", 0)
    estimated = round(sum(float(e.get("cost") or 0) for e in events
                          if (e.get("t") or 0) >= since), 6)

    factor = None
    if spent and estimated > 0:
        raw = spent / estimated
        if 0.2 <= raw <= 5:
            factor = round(raw, 3)

    return {
        "ok": bool(result.get("ok")),
        "error": result.get("error", ""),
        "total": (last or {}).get("total"),
        "currency": (last or {}).get("currency", "CNY"),
        "at": (last or {}).get("t"),
        "source": result.get("source", ""),
        "first": first,
        "spent": spent,
        "estimated": estimated,
        "factor": factor,
        "account": account,
    }
