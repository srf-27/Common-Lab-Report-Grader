"""agreement.py 自检：已知小样本手算值 + 退化用例断言。"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.nodes.agreement import (
    cohen_kappa, weighted_kappa, krippendorff_alpha, agreement_report)

# 完全一致 → 三项指标均为 1（有多个类别，避免期望一致率=1 的退化）
perfect = [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"), ("E", "E")]
assert cohen_kappa(perfect) == 1.0
assert weighted_kappa(perfect) == 1.0
assert krippendorff_alpha(perfect) == 1.0

# 手算用例：4 单元 (A,A),(A,B),(B,B),(B,A)；dist(A,B)=1/16，N=8
pairs = [("A", "A"), ("A", "B"), ("B", "B"), ("B", "A")]
# Cohen κ：po=0.5，边际 0.5/0.5 → pe=0.5 → 0.0
assert abs(cohen_kappa(pairs) - 0.0) < 1e-12
# 加权 κ：po_bar = 1-0.03125 = 0.96875，加权期望 pe_bar 也 = 0.96875 → 0（边际对称）
assert abs(weighted_kappa(pairs) - 0.0) < 1e-12
# α：1 - 2Σd(N-1)/Σwd = 1 - (1/4)*7/2 = 0.125（已用 krippendorff 参考包 499 例交叉验证）
assert abs(krippendorff_alpha(pairs) - 0.125) < 1e-12

# 全部同一类别 → 期望一致率=1，返回 None 而非除零
same = [("C", "C")] * 5
assert cohen_kappa(same) is None
assert krippendorff_alpha([("C", "C")]) is None  # n<2
assert weighted_kappa(same) == 1.0

# 非法等级被过滤
assert cohen_kappa([("X", "A"), ("A", "A")]) is None  # 过滤后 n=1 但同类别 → None
assert krippendorff_alpha([("X", "A")]) is None  # 过滤后 n=0
assert cohen_kappa([]) is None

# agreement_report 结构
report = agreement_report(
    [{"status": "graded", "report_id": "r1",
      "grading": {"scores": {"内容": {"ai_level": "A", "level": "B"}}}}],
    {"criteria": [{"name": "内容"}]},
    {"r1": {"内容": "A"}})
d = report["dimensions"]["内容"]
assert d["cohen_kappa"] is None and d["weighted_kappa"] == 1.0 and d["n"] == 1
assert d["krippendorff_alpha"] is None and d["confusion"] == {"A->A": 1}

# 常数评分者：加权 κ 与 Cohen κ 都应为 0（修正前会虚高）
const = [("E", "B")] * 5 + [("E", "C")] * 11 + [("E", "D")] * 7
assert abs(weighted_kappa(const)) < 1e-12
assert abs(cohen_kappa(const)) < 1e-12

print("agreement selfcheck: all assertions passed")
