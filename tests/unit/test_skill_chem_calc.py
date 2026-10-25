"""chem_calc 技能包：数值正确性与契约（TOOLS_SCHEMA/dispatch 与 calc_tools 同构）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.utils import skills


def test_skill_discovered_and_contract():
    names = [s["name"] for s in skills.list_skills()]
    assert "chem_calc" in names
    skill = next(s for s in skills.list_skills() if s["name"] == "chem_calc")
    assert skill["tools"] == ["chem_molarity", "chem_titration", "chem_yield"]
    assert skill["desc"].startswith("化学计算")


def test_molarity_and_yield():
    module = skills.load("chem_calc")
    out = module.dispatch("chem_molarity", {"mass_g": 5.85, "molar_mass": 58.5, "volume_l": 0.5})
    assert abs(out["molarity"] - 0.2) < 1e-12
    out = module.dispatch("chem_yield", {"actual": 4.2, "theoretical": 5.0})
    assert abs(out["yield_percent"] - 84.0) < 1e-9


def test_titration_solves_missing():
    module = skills.load("chem_calc")
    out = module.dispatch("chem_titration", {"c1": 0.1, "v1": 20.0, "n1": 1,
                                             "c2": None, "v2": 25.0, "n2": 2})
    assert abs(out["c2"] - 0.04) < 1e-12  # c2 = c1·v1·n1/(v2·n2)
    try:
        module.dispatch("chem_titration", {"c1": 0.1, "v1": None, "n1": 1,
                                           "c2": None, "v2": 25.0, "n2": 2})
        raise AssertionError("两个未知项应拒绝")
    except ValueError:
        pass


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_skill_chem_calc ok")
