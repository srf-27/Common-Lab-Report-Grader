import re

_OPS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
}


def _verify_one(text, rules):
    rtype = rules.get("type")
    try:
        if rtype in ("exists", "contains"):
            m = re.search(rules["pattern"], text)
            return {"verdict": "ok", "passed": bool(m),
                    "detail": f"{'找到' if m else '未找到'}匹配「{rules['pattern']}」"}
        if rtype == "numeric_compare":
            m = re.search(rules["pattern"], text)
            if not m:
                return {"verdict": "ok", "passed": False, "detail": f"未从报告提取到匹配「{rules['pattern']}」的数值"}
            value = float(m.group(1))
            ok = _OPS[rules.get("op", "<=")](value, float(rules["threshold"]))
            return {"verdict": "ok", "passed": ok,
                    "detail": f"提取值 {value} {rules.get('op')} {rules['threshold']} → {'通过' if ok else '不通过'}"}
    except (KeyError, re.error, ValueError, IndexError) as e:
        return {"verdict": "unsupported", "passed": None, "detail": f"规则执行失败（{e}），回退 LLM 判分"}
    return {"verdict": "unsupported", "passed": None, "detail": f"未知规则类型 {rtype}，回退 LLM 判分"}


def verify(text, rules):
    if isinstance(rules, dict):
        rules = [rules]
    if not rules or not isinstance(rules, list):
        return {"verdict": "unsupported", "passed": None, "detail": "规则缺失，需 LLM 判分"}
    results = [_verify_one(text, r) for r in rules]
    for r in results:
        if r["verdict"] != "ok":
            return r
    passed = all(r["passed"] for r in results)
    return {"verdict": "ok", "passed": passed,
            "detail": "；".join(r["detail"] for r in results)}
