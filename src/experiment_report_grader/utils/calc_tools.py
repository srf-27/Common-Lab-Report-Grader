"""判级验算工具包：声明为 OpenAI tools，模型对数值结论（计算、不确定度、拟合）先调用再下等级。"""

import ast
import math
import statistics

_FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
          "exp": math.exp, "log": math.log, "log10": math.log10, "abs": abs}
_CONSTS = {"pi": math.pi, "e": math.e}
_BINOPS = {ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow}
_UNARY = {ast.USub, ast.UAdd}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left, right = _eval(node.left), _eval(node.right)
        return {ast.Add: lambda: left + right, ast.Sub: lambda: left - right,
                ast.Mult: lambda: left * right, ast.Div: lambda: left / right,
                ast.FloorDiv: lambda: left // right, ast.Mod: lambda: left % right,
                ast.Pow: lambda: left ** right}[type(node.op)]()
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        value = _eval(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in _FUNCS and not node.keywords:
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError(f"不允许的表达式元素: {type(node).__name__}")


def calc_eval(expression):
    value = _eval(ast.parse(str(expression), mode="eval"))
    return {"value": value}


def calc_stats(values, instrument_error=0.0):
    values = [float(v) for v in values]
    if len(values) < 2:
        raise ValueError("至少两个数值")
    mean = statistics.fmean(values)
    std = statistics.stdev(values)
    ua = std / math.sqrt(len(values))
    ub = float(instrument_error or 0.0) / math.sqrt(3)
    return {"n": len(values), "mean": mean, "std": std,
            "ua": ua, "ub": ub, "u": math.sqrt(ua * ua + ub * ub),
            "result": f"{mean} ± {math.sqrt(ua * ua + ub * ub)}"}


def calc_fit(xs, ys):
    xs, ys = [float(v) for v in xs], [float(v) for v in ys]
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("xs/ys 长度需一致且至少两点")
    n = len(xs)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    syy = sum((y - my) ** 2 for y in ys)
    r = sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else None
    return {"n": n, "slope": slope, "intercept": intercept, "r": r}


TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "calc_eval",
        "description": "按运算优先级求值数学表达式。支持 + - * / // % ** 与 sqrt/sin/cos/tan/exp/log/log10/abs、"
                       "常量 pi/e。用于复算报告里的公式与数值结论。",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string", "description": "如 (23.45e-6)/(4*10*589.3e-9)"}},
            "required": ["expression"]}}},
    {"type": "function", "function": {
        "name": "calc_stats",
        "description": "多次测量统计：均值、标准差、A 类不确定度、与仪器误差（B 类，均匀分布）合成后的不确定度。",
        "parameters": {"type": "object", "properties": {
            "values": {"type": "array", "items": {"type": "number"}},
            "instrument_error": {"type": "number", "description": "仪器最大允差，可选"}},
            "required": ["values"]}}},
    {"type": "function", "function": {
        "name": "calc_fit",
        "description": "最小二乘线性拟合 y = slope*x + intercept，返回斜率、截距与相关系数 r。",
        "parameters": {"type": "object", "properties": {
            "xs": {"type": "array", "items": {"type": "number"}},
            "ys": {"type": "array", "items": {"type": "number"}}},
            "required": ["xs", "ys"]}}},
]

_IMPL = {"calc_eval": calc_eval, "calc_stats": calc_stats, "calc_fit": calc_fit}


def dispatch(name, arguments):
    fn = _IMPL.get(name)
    if fn is None:
        raise ValueError(f"未知工具: {name}")
    return fn(**(arguments or {}))
