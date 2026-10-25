"""基准全链路跑一遍：报告 → 提取 → 后台评分 → debug 页一致性分析（κ / 加权 κ / α）。

用法：python tests/integration/bench_run.py [bench目录]
默认 tests/fixtures/bench/cn_lab。会调用真实 LLM（产生费用），约 10-40 分钟。
"""

import io
import json
import os
import pathlib
import shutil
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

BENCH = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/bench/cn_lab")
import experiment_report_grader.app as app_mod  # noqa: E402
from experiment_report_grader.nodes.agreement import agreement_report, weighted_kappa  # noqa: E402

client = app_mod.app.test_client()
state = app_mod.state


def poll(url, key, done, timeout=7200):
    start = time.time()
    while time.time() - start < timeout:
        data = client.get(url).get_json() or {}
        if data.get(key) in done:
            return data
        time.sleep(3)
    return {"timeout": True}


report_dir = BENCH / "reports" if (BENCH / "reports").is_dir() else BENCH
reports = sorted(p for p in report_dir.iterdir()
                 if p.suffix.lower() in (".md", ".txt", ".docx", ".pdf", ".doc"))
criteria_file = next((p for p in (BENCH / "criteria.txt", BENCH / "grading_criteria.txt")
                      if p.exists()), None)
print("1) 新建课程:", client.post("/session/new",
                                 data={"name": f"基准评测({len(reports)}份/{BENCH.name})"}).status_code)
with open(criteria_file, "rb") as f:
    client.post("/upload_criteria", data={"criteria_file": (io.BytesIO(f.read()), criteria_file.name)})
rubric = {}
for attempt in range(1, 4):
    client.post("/process_criteria")
    task = poll("/task_status", "status", {"done", "error", "cancelled"})
    print(f"2) 生成评审标准(第{attempt}次):", task.get("status"), task.get("error") or "", flush=True)
    rubric = state.get("rubric_json") or {}
    if rubric.get("criteria"):
        break
if not rubric.get("criteria"):
    sys.exit("评审标准生成失败，终止")
print("   维度:", [c["name"] for c in rubric.get("criteria", [])],
      "| 机械判决项:", [c["name"] for c in rubric.get("criteria", []) if c.get("mechanical")])

files = [(io.BytesIO(p.read_bytes()), p.name) for p in reports]
print("3) 上传", len(files), "份报告:", client.post(
    "/upload_reports", data={"report_files": files}, content_type="multipart/form-data").status_code,
    flush=True)
client.post("/process_reports")
print("4) 提取:", poll("/task_status", "status", {"done", "error", "cancelled"}), flush=True)

teacher = json.loads((BENCH / "teacher_grades.json").read_text(encoding="utf-8"))
shutil.copyfile(BENCH / "teacher_grades.json", pathlib.Path(app_mod.session_dir()) / "teacher_grades.json")

names = [r["meta"]["filename"] for r in state["extracted_reports"] if r.get("status") == "ok"]
print("5) 开始后台评分（", len(names), "份 ）:", client.post("/start_grading", data={"report_ids": names}).status_code,
      flush=True)
status = poll("/grading_status", "phase", {"done", "error", "cancelled"})
print("   评分结束:", status, flush=True)

results = state["grader"].results if state.get("grader") else []
graded = [r for r in results if r.get("status") == "graded"]
print("   已评", len(graded), "份；注入标记", len([r for r in results if r.get("status") == "flagged_injection"]),
      "；相似告警", len([r for r in results if r.get("similarity_warnings")]))

for r in graded:
    entry = next((e for e in state["extracted_reports"] if e["meta"]["filename"] == r["report_id"]), None)
    if entry:
        entry["status"] = "ok"
if len(sys.argv) < 3 or sys.argv[2] != "no-finalize":  # 一致性评测不需要终审入 RAG（省 LLM 脱敏时间）
    for r in graded:
        client.post(f"/approve_report/{r['report_id']}")

agreement = agreement_report(results, rubric, teacher)
page = client.get("/api/results")
counts = (page.get_json() or {}).get("counts", {})
print("6) 结果接口:", page.status_code, "| 已评:", counts.get("graded"), "| 失败:", counts.get("failed"))


def fmt(v):
    return "—" if v is None else round(v, 3)


print("7) 一致性指标（AI vs 教师）:")
for label, key in (("Cohen's κ（未加权）", "cohen_kappa"), ("二次加权 κ", "weighted_kappa"),
                   ("Krippendorff's α", "krippendorff_alpha")):
    overall = agreement["overall"]
    print(f"   总体 {label} = {fmt(overall[key])} | n = {overall['n']}")
for name, detail in agreement["dimensions"].items():
    diffs = {k: v for k, v in detail["confusion"].items() if k.split("->")[0] != k.split("->")[1]}
    print(f"   {name}: κ = {fmt(detail['cohen_kappa'])} | 加权κ = {fmt(detail['weighted_kappa'])}"
          f" | α = {fmt(detail['krippendorff_alpha'])} | n = {detail['n']} | 分歧 {diffs}")


def band(percent):
    return "A" if percent >= 90 else "B" if percent >= 80 else \
           "C" if percent >= 70 else "D" if percent >= 60 else "E"


band_pairs, band_confusion = [], {}
for r in graded:
    teacher_band = (teacher.get(r["report_id"]) or {}).get("总分")
    total = ((r.get("grading") or {}).get("subtotals") or {}).get("total")
    if teacher_band and total is not None:
        ai_band = band(total)
        band_pairs.append((ai_band, teacher_band))
        key = f"{ai_band}->{teacher_band}"
        band_confusion[key] = band_confusion.get(key, 0) + 1
overall_band = weighted_kappa(band_pairs)
print("8) 总分档位 κ（AI 总分档 vs 专家分档）= ",
      "样本不足" if overall_band is None else round(overall_band, 3),
      "| n =", len(band_pairs), "| 混淆:", band_confusion)
report_lines = [f"基准: {BENCH}", f"报告数: {len(reports)}",
                f"总分档位 κ: {overall_band}", f"pair n: {len(band_pairs)}",
                f"混淆: {band_confusion}", f"分维度: {agreement}"]
(pathlib.Path(app_mod.session_dir()) / "agreement_result.txt").write_text(
    "\n".join(str(line) for line in report_lines), encoding="utf-8")
print("9) 结果已写入:", pathlib.Path(app_mod.session_dir()) / "agreement_result.txt")
