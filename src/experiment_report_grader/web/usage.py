"""按课程统计模型 token 与费用：写 <课程>/usage.json，切换课程互不影响。

计价的获取与计算方式对齐 cc-switch：四槽单价（输入/输出/缓存读/缓存写）× 各项
token ÷ 1e6，价目优先级 用户覆盖 > models.dev 同步（≤6h）> 内置表，见 web/pricing.py。
无定价模型金额记 0 并标 unpriced；币种随价目（事件带 cur 字段）。
"""

import os
import threading
import time

from .. import storage
from ..utils.llm_client import LLMClient, openai_client
from . import pricing

MAX_EVENTS = 600

_LOCK = threading.Lock()
_CTX = threading.local()


def set_report(report_id=None):
    """标记「当前线程正在处理哪份报告」，让每次调用都能归到具体报告上。"""
    _CTX.report = report_id


def current_report():
    return getattr(_CTX, "report", None)


def empty():
    return {"cost": 0.0, "tokens_in": 0, "tokens_cached": 0, "tokens_out": 0,
            "calls": 0, "errors": 0, "model": "", "seq": 0, "events": []}


def path_for(session_dir):
    return os.path.join(session_dir, "usage.json")


def load(session_dir):
    data = empty()
    saved = storage.read_json(path_for(session_dir), None)
    if isinstance(saved, dict):
        for key in data:
            if key in saved:
                data[key] = saved[key]
        if not isinstance(data["events"], list):
            data["events"] = []
    repriced = False
    for event in data["events"]:
        if event.get("src") == "legacy" and not event.get("priced"):
            amount, cur = pricing.cost_of(event.get("m"),
                                          (event.get("i") or 0) - (event.get("c") or 0),
                                          event.get("c") or 0, 0, event.get("o") or 0)
            if amount is None:
                amount = 0.0
            event["cost"] = round(amount, 6)
            event["cur"] = cur or "USD"
            event["priced"] = True
            repriced = True
    if repriced:
        # 旧版只存了总数，价格是老的（2/8）：按现在的价目表重算，总额也跟着修
        data["cost"] = round(sum(e["cost"] for e in data["events"]), 6)
        try:
            _write(session_dir, data)
        except OSError:
            pass
    if not data["events"] and data["calls"]:
        # 旧版只存了累计值：补一条汇总事件，否则「今天/趋势」会是空的
        data["events"] = [{
            "t": int(os.path.getmtime(path_for(session_dir))
                     if os.path.exists(path_for(session_dir)) else time.time()),
            "m": data["model"] or "-", "i": data["tokens_in"], "c": data["tokens_cached"],
            "o": data["tokens_out"], "cost": data["cost"], "ms": 0,
            "s": "ok", "src": "legacy",
        }]
    return data


def _write(session_dir, data):
    storage.write_json(path_for(session_dir), data)


def _cached_tokens(usage):
    """DeepSeek 把命中数放在扩展字段里（model_extra），OpenAI 放在 details.cached_tokens。"""
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) if details else 0
    if not cached:
        cached = getattr(usage, "prompt_cache_hit_tokens", 0) or 0
    if not cached:
        extra = getattr(usage, "model_extra", None) or {}
        cached = extra.get("prompt_cache_hit_tokens") or 0
    return int(cached or 0)


def estimate(text):
    """没有 usage 的接口（ollama / 自定义网关）按字符估算：中文 0.6 token/字，其余 0.3。"""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return max(1, round(cjk * 0.6 + (len(text) - cjk) * 0.3))


def record(session_dir, model, tokens_in, tokens_cached, tokens_out,
           ms=0, status="ok", source=""):
    tokens_cached = min(max(0, tokens_cached), tokens_in)
    now = time.time()
    amount, currency = pricing.cost_of(model, tokens_in - tokens_cached, tokens_cached,
                                       0, tokens_out)
    unpriced = amount is None
    if unpriced:
        amount = 0.0
    with _LOCK:
        data = load(session_dir)
        data["cost"] = round(data["cost"] + amount, 6)
        data["tokens_in"] += int(tokens_in)
        data["tokens_cached"] += int(tokens_cached)
        data["tokens_out"] += int(tokens_out)
        data["calls"] += 1
        if status != "ok":
            data["errors"] += 1
        data["seq"] += 1
        data["model"] = model or data["model"]
        data["events"].append({
            "t": int(now), "m": model or "-", "i": int(tokens_in), "c": int(tokens_cached),
            "o": int(tokens_out), "cost": round(amount, 6), "ms": int(ms),
            "s": status, "src": source, "r": current_report(),
            "cur": currency or "-", "unpriced": unpriced or None,
        })
        data["events"] = data["events"][-MAX_EVENTS:]
        _write(session_dir, data)
    _sync_state(session_dir, data)
    return data


def _sync_state(session_dir, data):
    """后台线程也在写：让 /api/usage 直接读内存，不必每次读盘。"""
    from .state import session_dir as current_dir, state

    if not state.get("session"):
        return
    if os.path.abspath(current_dir()) == os.path.abspath(session_dir):
        state["usage"] = data


def payload(session_dir, days=1, model=None):
    data = load(session_dir)
    now = int(time.time())
    if model:
        events = [e for e in data["events"] if e.get("m") == model]
        if days:
            since = now - days * 86400
            events = [e for e in events
                      if e.get("t", 0) >= since and e.get("src") != "legacy"]
        summary = {
            "cost": round(sum(e["cost"] for e in events), 6),
            "tokens_in": sum(e["i"] for e in events),
            "tokens_cached": sum(e["c"] for e in events),
            "tokens_out": sum(e["o"] for e in events),
            "calls": len(events),
            "errors": sum(1 for e in events if e.get("s") != "ok"),
        }
    elif days:
        since = now - days * 86400
        # 旧汇总事件是按总量估算的一条假记录（没有缓存明细），混进当天会虚高
        events = [e for e in data["events"]
                  if e.get("t", 0) >= since and e.get("src") != "legacy"]
        summary = {
            "cost": round(sum(e["cost"] for e in events), 6),
            "tokens_in": sum(e["i"] for e in events),
            "tokens_cached": sum(e["c"] for e in events),
            "tokens_out": sum(e["o"] for e in events),
            "calls": len(events),
            "errors": sum(1 for e in events if e.get("s") != "ok"),
        }
    else:
        events = list(data["events"])
        summary = {key: data[key] for key in
                   ("cost", "tokens_in", "tokens_cached", "tokens_out", "calls", "errors")}

    saving = 0.0
    for event in events:
        price = pricing.lookup(event.get("m"))
        if price:
            saving += (event.get("c") or 0) * (price["input"] - price["cache_read"]) / 1_000_000
    attributed = [e for e in events if e.get("r")]
    reports = len({e["r"] for e in attributed})
    report_cost = round(sum(e["cost"] for e in attributed), 6)

    summary["cache_rate"] = (summary["tokens_cached"] / summary["tokens_in"]
                             if summary["tokens_in"] else 0.0)
    summary["cache_saving"] = round(saving, 6)
    summary["reports"] = reports
    summary["report_cost"] = report_cost
    summary["cost_per_report"] = round(report_cost / reports, 4) if reports else None
    summary["seq"] = data["seq"]
    summary["model"] = data["model"]
    by_currency = {}
    for event in events:
        cur = event.get("cur") or "USD"
        by_currency[cur] = round(by_currency.get(cur, 0.0) + (event.get("cost") or 0), 6)
    summary["cost_by_currency"] = by_currency
    summary["unpriced_calls"] = sum(1 for e in events if e.get("unpriced"))

    buckets, models = {}, {}
    if days == 1:
        # 今天：从 00:00 到 23:00 固定 24 个桶，没有调用的时段补 0，
        # 否则稀疏数据会挤在同一个 x 坐标上，看起来像坏图
        local = time.localtime(now)
        midnight = int(time.mktime((local.tm_year, local.tm_mon, local.tm_mday,
                                    0, 0, 0, 0, 0, -1)))
        for hour in range(24):
            buckets[midnight + hour * 3600] = {"t": midnight + hour * 3600, "i": 0, "c": 0,
                                               "o": 0, "cost": 0.0, "calls": 0}
    elif days > 1:
        local = time.localtime(now)
        for offset in range(days - 1, -1, -1):
            day = int(time.mktime((local.tm_year, local.tm_mon, local.tm_mday - offset,
                                   0, 0, 0, 0, 0, -1)))
            buckets[day] = {"t": day, "i": 0, "c": 0, "o": 0, "cost": 0.0, "calls": 0}
    for event in events:
        span = 3600 if days <= 1 else 86400
        hour = event["t"] - event["t"] % span
        bucket = buckets.setdefault(hour, {"t": hour, "i": 0, "c": 0, "o": 0,
                                           "cost": 0.0, "calls": 0})
        bucket["i"] += event["i"]
        bucket["c"] += event["c"]
        bucket["o"] += event["o"]
        bucket["cost"] = round(bucket["cost"] + event["cost"], 6)
        bucket["calls"] += 1
        item = models.setdefault(event["m"], {"model": event["m"], "calls": 0, "i": 0,
                                              "c": 0, "o": 0, "cost": 0.0, "ms": 0, "errors": 0})
        item["calls"] += 1
        item["i"] += event["i"]
        item["c"] += event["c"]
        item["o"] += event["o"]
        item["cost"] = round(item["cost"] + event["cost"], 6)
        item["ms"] += event["ms"]
        if event.get("s") != "ok":
            item["errors"] += 1

    for item in models.values():
        item["avg_ms"] = round(item["ms"] / item["calls"]) if item["calls"] else 0

    return {
        "summary": summary,
        "events": sorted(events, key=lambda e: e["t"], reverse=True)[:200],
        "buckets": sorted(buckets.values(), key=lambda b: b["t"]),
        "models": sorted(models.values(), key=lambda m: m["cost"], reverse=True),
        "pricing_source": "models.dev（同步）+ 内置快照，覆盖见 data/output/pricing_overrides.json",
        "now": now,
    }


class MeteredLLM(LLMClient):
    """记录用量后再返回原文，行为与 LLMClient 完全一致。"""

    def __init__(self, config=None):
        super().__init__(config)
        from .state import state

        self.session_id = state.get("session")

    def _bump(self, model, tokens_in, tokens_cached, tokens_out, ms, status="ok"):
        from .state import session_dir

        if self.session_id:
            record(session_dir(self.session_id), model, tokens_in, tokens_cached,
                   tokens_out, ms=ms, status=status, source=self.backend)

    def _chat_openai(self, messages, temperature, tools=None, tool_executor=None,
                     max_tokens=None):
        def bill(resp, started, status="ok"):
            if not self.session_id:
                return
            model = self.config["openai"]["model"]
            ms = int((time.perf_counter() - started) * 1000)
            if resp is None:
                self._bump(model, 0, 0, 0, ms, "error")
                return
            content = resp.choices[0].message.content or ""
            usage = getattr(resp, "usage", None)
            if usage is None:
                prompt = "".join(str(m.get("content", "")) for m in messages)
                self._bump(model, estimate(prompt), 0, estimate(content), ms)
            else:
                self._bump(model, getattr(usage, "prompt_tokens", 0) or 0,
                           _cached_tokens(usage),
                           getattr(usage, "completion_tokens", 0) or 0, ms)

        return super()._chat_openai(messages, temperature, tools=tools,
                                    tool_executor=tool_executor, max_tokens=max_tokens,
                                    on_response=bill)

    def chat(self, messages, temperature=0.3, retries=2, **kwargs):
        started = time.perf_counter()
        text = super().chat(messages, temperature=temperature, retries=retries, **kwargs)
        if self.backend != "openai" and text:
            model = (self.config.get(self.backend) or {}).get("model", self.backend)
            prompt = "".join(str(m.get("content", "")) for m in messages)
            self._bump(model, estimate(prompt), 0, estimate(text),
                       int((time.perf_counter() - started) * 1000))
        return text

    def chat_stream(self, messages, temperature=0.3, max_tokens=None,
                    tools=None, tool_executor=None):
        """流式版计费：事件原样透传，聚合 answer 与 usage 记账（缺失 usage 时按字符估算）。"""
        if tools and tool_executor:
            text = self.chat(messages, temperature=temperature, max_tokens=max_tokens,
                             tools=tools, tool_executor=tool_executor)
            yield "answer", text
            yield "usage", {}
            return
        started = time.perf_counter()
        model = (self.config.get("openai") or {}).get("model", "-")
        answer, usage = [], None
        try:
            for kind, payload in super().chat_stream(messages, temperature=temperature):
                if kind == "answer" and payload:
                    answer.append(payload)
                elif kind == "usage" and payload:
                    usage = payload
                yield kind, payload
        except Exception:
            self._bump(model, 0, 0, 0, int((time.perf_counter() - started) * 1000), "error")
            raise
        ms = int((time.perf_counter() - started) * 1000)
        if usage is not None:
            self._bump(model, getattr(usage, "prompt_tokens", 0) or 0,
                       _cached_tokens(usage), getattr(usage, "completion_tokens", 0) or 0, ms)
        else:
            prompt = "".join(str(m.get("content", "")) for m in messages)
            self._bump(model, estimate(prompt), 0, estimate("".join(answer)), ms)
