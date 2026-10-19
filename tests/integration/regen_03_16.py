"""定向重生成 03（补全）与 16（贯彻及格缺陷），幂等。"""
import importlib.util
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

spec = importlib.util.spec_from_file_location("b", pathlib.Path(__file__).parent / "build_cn_lab_bench.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

from convert_cn_lab_docx import convert  # noqa: E402
from experiment_report_grader.utils.llm_client import LLMClient, load_config  # noqa: E402

ROOT = pathlib.Path("tests/fixtures/bench/cn_lab")
llm = LLMClient(load_config())

jobs = {
    "cn_lab_03.md": build.GENERATE_PROMPT.format(
        template=build.TEMPLATE_SPEC, defect=build.PLAN[2][4],
        l_val=1.08, d_val=1.12, b_val=79.8, dia_val=0.602, dn_val=1.61)
    + "\n补充硬性要求：必须完整写完全部章节，最后是【思考和讨论】（问题与解决办法、工程应用讨论、改进设计各至少两句），以完整句子结尾。",
    "cn_lab_16.md": build.GENERATE_PROMPT.format(
        template=build.TEMPLATE_SPEC,
        defect="及格（硬性约束）：全文禁止出现【实验仪器】和【思考和讨论】章节；实验步骤只有两三行；"
               "误差分析只有一句套话（如「误差主要来自读数误差」）；结论含糊只有一句（如「实验基本完成了」）；"
               "数据单位有 2 处错误（如把 mm 写成 cm）；全文 1200–1800 字",
        l_val=1.02, d_val=1.24, b_val=75.0, dia_val=0.550, dn_val=1.50)
    + "\n补充硬性要求：禁止的章节绝对不能出现；以完整句子结尾。",
}

for fn, prompt in jobs.items():
    md_path = ROOT / "reports_md" / fn
    if md_path.exists():
        old = md_path.read_text(encoding="utf-8")
        if "思考" in old and "讨论" in old and len(old) > 2500 and fn.endswith("03.md"):
            print(fn, "已达标，跳过", flush=True)
            continue
    for attempt in range(4):
        text = llm.chat([{"role": "user", "content": prompt}], temperature=0.85)
        text = re.sub(r"^```markdown\s*", "", (text or "").strip())
        text = re.sub(r"\n```$", "\n", text)
        if fn.endswith("03.md"):
            ok = "思考" in text and "讨论" in text and len(text) > 2500
        else:
            ok = "实验仪器" not in text and "思考" not in text and 800 < len(text) < 2400
        print(fn, "第", attempt + 1, "次:", len(text or ""), "字 ok=", ok, flush=True)
        if ok:
            md_path.write_text(text + "\n", encoding="utf-8")
            convert(md_path, ROOT / "reports" / fn.replace(".md", ".docx"))
            break
    else:
        raise SystemExit(fn + " 仍不达标")
print("done")
