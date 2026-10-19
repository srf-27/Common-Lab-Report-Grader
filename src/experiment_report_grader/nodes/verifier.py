"""机械判决项的裁判：代码由 LLM 依据机械判决项生成，本模块负责生成、校验与执行。

LLM 生成失败或执行异常时，回退到 rules 规则解释器（见文件末尾）。
"""

import ast
import builtins
import json
import math
import re

VERIFIER_TEMPLATE = '''参考模板（生成代码保持同样的接口）：

```python
import re


def verify(text):
    """逐条检查机械判决项，返回 {维度名: {"passed": bool|None, "detail": "判定依据"}}。"""
    results = {}
    hit = re.search(r"不确定度|误差传递", text)
    results["误差分析"] = {
        "passed": bool(hit),
        "detail": "命中「不确定度/误差传递」" if hit else "未找到误差分析表述",
    }
    return results
```
'''

VERIFIER_PROMPT = """你是评分系统的机械判决器作者。下面是评分细则中「可程序化判定」的维度，请为它们写一个 Python 裁判函数。

## 机械判决项（维度名 / 标准文档位置 / 规则提示 / 各级描述）
{criteria}

## {template}

## 硬性要求
1. 只输出 Python 代码（不要解释、不要 Markdown 围栏），必须定义 `def verify(text):`
2. 返回 dict，键名与上面列出的维度名完全一致，值为 {{"passed": true/false/None, "detail": "可核对的依据，含命中的原文片段"}}
3. 只允许 import re / math / json；禁止读写文件、联网、open/exec/eval
4. 判定必须可核对：优先用规则提示里的正则；数值比较用捕获组 + 阈值；证据不足时 passed 用 None
5. 覆盖每一个机械维度且不新增维度；同名维度只出现一次
"""

_ALLOWED_IMPORTS = {"re", "math", "json"}
_FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "input", "globals", "locals",
                    "vars", "getattr", "setattr", "delattr", "__import__"}


def _extract_code(text):
    match = re.search(r"```(?:python)?\s*(.*?)```", text or "", re.S)
    return (match.group(1) if match else (text or "")).strip()


def _validate(code):
    """静态检查 LLM 生成的代码：只允许白名单 import，禁用危险名字。"""
    tree = ast.parse(code)
    for node in ast.walk(tree):
        modules = set()
        if isinstance(node, ast.Import):
            modules = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            modules = {(node.module or "").split(".")[0]}
        if not modules <= _ALLOWED_IMPORTS:
            raise ValueError(f"verifier 引用了不允许的模块：{sorted(modules - _ALLOWED_IMPORTS)}")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise ValueError(f"verifier 使用了禁止的名字：{node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("verifier 含双下划线属性访问")
    return tree


def generate(criteria, llm):
    """让 LLM 依据机械判决项生成 verifier 代码；生成后立即静态校验。"""
    prompt = VERIFIER_PROMPT.format(
        criteria=json.dumps(criteria, ensure_ascii=False, indent=2),
        template=VERIFIER_TEMPLATE,
    )
    code = _extract_code(llm.chat([{"role": "user", "content": prompt}], temperature=0.1))
    _validate(code)
    return code


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split(".")[0] not in _ALLOWED_IMPORTS:
        raise ImportError(f"verifier 不允许 import {name}")
    return __import__(name, globals, locals, fromlist, level)


_SAFE_BUILTINS = {
    name: getattr(builtins, name)
    for name in dir(builtins)
    if not name.startswith("__") and name not in _FORBIDDEN_NAMES
}
_SAFE_BUILTINS["__import__"] = _safe_import


def run(code, text):
    """执行生成的 verifier，返回 {维度名: {"passed":..., "detail":...}}。

    本地小应用，直接在主进程跑：AST 白名单校验 + 受限 builtins 拦截危险操作。
    """
    _validate(code)
    namespace = {"__builtins__": _SAFE_BUILTINS, "re": re, "json": json, "math": math}
    exec(compile(code, "<llm-verifier>", "exec"), namespace)
    verify_func = namespace.get("verify")
    if not callable(verify_func):
        raise ValueError("verifier 未定义 verify(text) 函数")
    results = verify_func(text)
    if not isinstance(results, dict):
        raise ValueError("verify(text) 必须返回 dict")
    return results


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
    """回退路径：解释 rubric 里的 rules（LLM 生成的 verifier 不可用时才用）。"""
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
