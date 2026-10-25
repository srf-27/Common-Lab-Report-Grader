"""模型计价：口径与获取方式对齐 cc-switch。

- 四槽单价（每百万 token）：input / output / cache_read / cache_write，币种随价目源（models.dev 为 USD）
- 价目优先级：用户覆盖（data/output/pricing_overrides.json）> models.dev 同步（≤6h，缓存
  pricing_cache.json，失败静默）> 内置快照
- 模型 ID 清洗后精确匹配（去 vendor/ 前缀、":" 后缀、"@"→"-"、日期后缀）
- 成本 = (新增输入×input + 缓存读×cache_read + 缓存写×cache_write + 输出×output) / 1e6；
  缺槽按 cc-switch 比例补：cache_read=0.1×input、cache_write=1.25×input
- 无定价模型：返回 None（调用方显示"未定价"，不计金额）
"""

import json
import os
import re
import threading
import time
import urllib.request

TTL_SECONDS = 6 * 3600
_DATE_SUFFIX = re.compile(r"-\d{8}$")

# models.dev 快照（USD / 百万 token），同步不可用时兜底
BUILTIN = {
    "deepseek/deepseek-flash": {"input": 0.15, "output": 0.6, "cache_read": 0.003},
    "deepseek/deepseek-v4-flash": {"input": 0.15, "output": 0.6, "cache_read": 0.003},
    "deepseek/deepseek-v4-pro": {"input": 0.66, "output": 1.98, "cache_read": 0.022},
    "openai/gpt-5-mini": {"input": 0.25, "output": 2, "cache_read": 0.025},
    "openai/gpt-5-nano": {"input": 0.05, "output": 0.4, "cache_read": 0.005},
    "openai/gpt-4.1-nano": {"input": 0.1, "output": 0.4, "cache_read": 0.025},
    "anthropic/claude-sonnet-4-5": {"input": 3, "output": 15, "cache_read": 0.3, "cache_write": 3.75},
    "anthropic/claude-haiku-4-5": {"input": 1, "output": 5, "cache_read": 0.1, "cache_write": 1.25},
    "google/gemini-pro-latest": {"input": 2, "output": 12, "cache_read": 0.2},
}

_LOCK = threading.Lock()
_cache = None

MODELS_DEV_URL = "https://models.dev/api.json"


def _output_folder():
    from .state import OUTPUT_FOLDER
    return OUTPUT_FOLDER


def _cache_path():
    return os.path.join(_output_folder(), "pricing_cache.json")


def _overrides_path():
    return os.path.join(_output_folder(), "pricing_overrides.json")


def clean_id(model_id):
    """cc-switch 的模型 ID 清洗：去 vendor/ 前缀、':' 后缀、'@'→'-'、日期后缀。"""
    mid = str(model_id or "").strip().lower()
    mid = mid.split("/", 1)[-1]
    mid = mid.split(":", 1)[0]
    mid = mid.replace("@", "-")
    mid = _DATE_SUFFIX.sub("", mid)
    return mid


def _normalize(entry):
    if not isinstance(entry, dict):
        return None
    try:
        raw_read = entry.get("cache_read")
        price = {
            "input": float(entry.get("input") or 0),
            "output": float(entry.get("output") or 0),
            "cache_read": float(raw_read) if raw_read is not None else 0.0,
            "cache_write": float(entry.get("cache_write") or 0),
            "currency": str(entry.get("currency") or "USD"),
        }
    except (TypeError, ValueError):
        return None
    if price["cache_read"] <= 0:
        price["cache_read"] = 0.1 * price["input"]
    if price["cache_write"] <= 0:
        price["cache_write"] = 1.25 * price["input"]
    return price if price["input"] or price["output"] else None


def _fetch_models_dev():
    req = urllib.request.Request(MODELS_DEV_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    table = {}
    for provider, block in (data or {}).items():
        models = (block or {}).get("models") if isinstance(block, dict) else None
        if not isinstance(models, dict):
            continue
        for model_id, info in models.items():
            if isinstance(info, dict) and isinstance(info.get("cost"), dict):
                table[f"{provider}/{model_id}"] = info["cost"]
    return table


def _load_synced():
    global _cache
    if _cache is not None:
        return _cache
    path = _cache_path()
    cached = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            cached = json.load(f)
    except (OSError, ValueError):
        pass
    if cached and time.time() - (cached.get("fetched_at") or 0) < TTL_SECONDS:
        _cache = cached.get("table") or {}
        return _cache
    try:
        table = _fetch_models_dev()
    except Exception:
        _cache = cached.get("table") or {} if cached else {}
        return _cache
    try:
        os.makedirs(_output_folder(), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"fetched_at": time.time(), "table": table}, f, ensure_ascii=False)
    except OSError:
        pass
    _cache = table
    return _cache


def _load_overrides():
    try:
        with open(_overrides_path(), "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def table():
    """合并后的价目：overrides > models.dev 同步 > 内置快照。键为清洗前的原始 ID。"""
    merged = dict(BUILTIN)
    merged.update(_load_synced())
    merged.update(_load_overrides())
    return merged


def lookup(model_id):
    """按清洗后的 ID 精确匹配（先裸名，再全名），返回四槽价或 None。"""
    prices = table()
    for key in (clean_id(model_id), str(model_id or "").strip().lower()):
        entry = prices.get(key)
        if entry is None:
            entry = next((v for k, v in prices.items() if clean_id(k) == key), None)
        if entry is not None:
            return _normalize(entry)
    return None


def cost_of(model_id, tokens_in_new, tokens_cache_read, tokens_cache_write, tokens_out):
    """返回 (金额, 币种)；未定价返回 (None, None)。"""
    price = lookup(model_id)
    if price is None:
        return None, None
    amount = (tokens_in_new * price["input"]
              + tokens_cache_read * price["cache_read"]
              + tokens_cache_write * price["cache_write"]
              + tokens_out * price["output"]) / 1_000_000
    return round(amount, 6), price["currency"]


def reset_cache():
    global _cache
    with _LOCK:
        _cache = None


if __name__ == "__main__":
    print(json.dumps(table(), ensure_ascii=False, indent=1)[:800])
