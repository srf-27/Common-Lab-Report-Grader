"""重生成不完整的报告（截断/缺章节），循环校验直到完整。"""

import importlib.util
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

spec = importlib.util.spec_from_file_location(
    "build_cn_lab_bench", pathlib.Path(__file__).parent / "build_cn_lab_bench.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

from experiment_report_grader.utils.llm_client import LLMClient, load_config  # noqa: E402

ROOT = pathlib.Path("tests/fixtures/bench/cn_lab")
BAD = json.loads(pathlib.Path("_regen_list.json").read_text(encoding="utf-8"))
FINISH_HINT = ("\n补充硬性要求：必须完整写完全部章节，最后一个章节是【思考和讨论】"
               "（含问题与解决办法、工程应用讨论、改进设计各至少一句），"
               "并以完整句子结尾，不允许中途停止。")

# 临时把 reports/ 里的 md 移走逻辑与主脚本一致：只针对 BAD 列表
plan = {fn: item for fn, item in ((p[0], p) for p in build.PLAN) if fn in BAD}
assert len(plan) == len(BAD), (len(plan), BAD)

llm = LLMClient(load_config())
config = load_config()

# 与 build_cn_lab_bench.main() 相同的参数表（按 PLAN 索引取值）
PARAMS = [(1.02, 1.20, 76.2, 0.548, 1.52), (0.96, 1.35, 72.5, 0.498, 1.38),
          (1.08, 1.12, 79.8, 0.602, 1.61), (1.00, 1.28, 74.6, 0.524, 1.45),
          (1.05, 1.18, 77.0, 0.572, 1.55), (0.98, 1.32, 71.8, 0.512, 1.42),
          (1.10, 1.15, 78.4, 0.536, 1.58), (1.01, 1.25, 73.9, 0.486, 1.36),
          (1.03, 1.22, 75.5, 0.558, 1.49), (0.97, 1.30, 76.8, 0.518, 1.44),
          (1.06, 1.10, 74.2, 0.590, 1.60), (0.99, 1.26, 72.0, 0.505, 1.40),
          (1.04, 1.16, 77.6, 0.566, 1.53), (1.07, 1.20, 71.0, 0.530, 1.47),
          (0.95, 1.40, 78.0, 0.494, 1.35), (1.02, 1.24, 75.0, 0.550, 1.50),
          (1.00, 1.30, 73.0, 0.520, 1.43), (1.09, 1.14, 76.0, 0.610, 1.62),
          (0.98, 1.28, 74.0, 0.500, 1.39), (1.03, 1.22, 75.4, 0.544, 1.51)]

for i, (fn, score, name, sid, defect) in enumerate(build.PLAN):
    if fn not in plan:
        continue
    l_val, d_val, b_val, dia_val, dn_val = PARAMS[i % len(PARAMS)]
    prompt = build.GENERATE_PROMPT.format(template=build.TEMPLATE_SPEC, defect=defect,
                                          l_val=l_val, d_val=d_val, b_val=b_val,
                                          dia_val=dia_val, dn_val=dn_val) + FINISH_HINT
    for attempt in range(4):
        text = llm.chat([{"role": "user", "content": prompt}], temperature=0.85)
        text = re.sub(r"^```markdown\s*", "", (text or "").strip())
        text = re.sub(r"\n```\s*$", "\n", text)
        ok_tail = bool(re.search(r"[。）)”\"0-9a-zA-Z]\s*$", text.rstrip()))
        has_disc = "思考" in text and "讨论" in text
        if ok_tail and has_disc and len(text) > 1800:
            (ROOT / "reports_md" / fn).write_text(text + "\n", encoding="utf-8")
            print(fn, "重生成 OK", len(text), "字（第", attempt + 1, "次）", flush=True)
            break
        print(fn, "第", attempt + 1, "次不完整:", len(text), "字 tail_ok=", ok_tail, flush=True)
    else:
        raise SystemExit(f"{fn} 多次重生成仍不完整")

# 更新 reports_md 与 docx
from convert_cn_lab_docx import convert  # noqa: E402
for fn in BAD:
    md = ROOT / "reports_md" / fn
    convert(md, ROOT / "reports" / (pathlib.Path(fn).stem + ".docx"))
print("docx 已同步更新")
