"""化学实验验算：摩尔浓度、滴定、产率。"""

TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "chem_molarity",
        "description": "由溶质质量（g）与摩尔质量（g/mol）配制成体积（L）溶液，返回摩尔浓度 mol/L。",
        "parameters": {"type": "object", "properties": {
            "mass_g": {"type": "number"}, "molar_mass": {"type": "number"},
            "volume_l": {"type": "number"}}, "required": ["mass_g", "molar_mass", "volume_l"]}}},
    {"type": "function", "function": {
        "name": "chem_titration",
        "description": "滴定计算：c1·v1·n1 = c2·v2·n2（浓度 mol/L、体积 mL、化学计量比 n）。"
                       "给出任三项求第四项（未知项传 null）。",
        "parameters": {"type": "object", "properties": {
            "c1": {"type": ["number", "null"]}, "v1": {"type": ["number", "null"]},
            "n1": {"type": "number"}, "c2": {"type": ["number", "null"]},
            "v2": {"type": ["number", "null"]}, "n2": {"type": "number"}},
            "required": ["n1", "n2"]}}},
    {"type": "function", "function": {
        "name": "chem_yield",
        "description": "产率 %：实际产量 / 理论产量 ×100（单位一致，g 或 mol）。",
        "parameters": {"type": "object", "properties": {
            "actual": {"type": "number"}, "theoretical": {"type": "number"}},
            "required": ["actual", "theoretical"]}}},
]


def chem_molarity(mass_g, molar_mass, volume_l):
    if volume_l <= 0 or molar_mass <= 0:
        raise ValueError("体积与摩尔质量必须大于 0")
    return {"molarity": mass_g / molar_mass / volume_l}


def chem_titration(c1=None, v1=None, n1=1, c2=None, v2=None, n2=1):
    known = [x is not None for x in (c1, v1, c2, v2)]
    if sum(known) != 3:
        raise ValueError("c1/v1/c2/v2 恰好给三项，未知项传 null")
    if c1 is None:
        return {"c1": c2 * v2 * n2 / (v1 * n1)}
    if v1 is None:
        return {"v1": c2 * v2 * n2 / (c1 * n1)}
    if c2 is None:
        return {"c2": c1 * v1 * n1 / (v2 * n2)}
    return {"v2": c1 * v1 * n1 / (c2 * n2)}


def chem_yield(actual, theoretical):
    if theoretical <= 0:
        raise ValueError("理论产量必须大于 0")
    return {"yield_percent": actual / theoretical * 100}


_IMPL = {"chem_molarity": chem_molarity, "chem_titration": chem_titration,
         "chem_yield": chem_yield}


def dispatch(name, arguments):
    fn = _IMPL.get(name)
    if fn is None:
        raise ValueError(f"未知工具: {name}")
    return fn(**(arguments or {}))
