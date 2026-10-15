import os
import re
import json
import time
import threading
import yaml
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from utils.llm_client import LLMClient, load_config
from utils.file_parser import collect_report_files
from nodes.report_extractor import ReportExtractor
from nodes.rubric_generator import RubricGenerator
from nodes.grader import Grader, _coerce_rubric
from nodes import rubric_io

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024
app.config["OUTPUT_FOLDER"] = os.path.join(os.path.dirname(__file__), "output")
app.config["SESSIONS_DIR"] = os.path.join(app.config["OUTPUT_FOLDER"], "sessions")
os.makedirs(app.config["SESSIONS_DIR"], exist_ok=True)

state = {
    "config": load_config(),
    "session": None,
    "rubric": None,
    "rubric_json": None,
    "criteria_doc": "",
    "extracted_reports": [],
    "grader": None,
    "pending_review": [],
    "corrections": {},
    "calibration": None,
    "grading_status": None,
    "grading_lock": threading.Lock(),
}

VALID_LEVELS = ("A", "B", "C", "D")


def _sessions_index_path():
    return os.path.join(app.config["OUTPUT_FOLDER"], "sessions.json")


def _load_sessions():
    p = _sessions_index_path()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"sessions": [], "current": None}


def _save_sessions(idx):
    with open(_sessions_index_path(), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)


def _session_dir(sid=None):
    sid = sid or state["session"]
    return os.path.join(app.config["SESSIONS_DIR"], sid)


def _session_sub(sub):
    d = os.path.join(_session_dir(), sub)
    os.makedirs(d, exist_ok=True)
    return d


def _approved_path():
    return os.path.join(_session_dir(), "approved.json")


def _load_approved():
    p = _approved_path()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def _save_approved(ids):
    with open(_approved_path(), "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False)


def _new_session(name):
    idx = _load_sessions()
    sid = "s_" + time.strftime("%Y%m%d_%H%M%S")
    entry = {"id": sid, "name": name.strip() or f"课程 {len(idx['sessions']) + 1}"}
    idx["sessions"].append(entry)
    idx["current"] = sid
    _save_sessions(idx)
    for sub in ("rubrics", "reports", "grading", "uploads"):
        os.makedirs(os.path.join(_session_dir(sid), sub), exist_ok=True)
    return entry


def _hydrate_session(sid):
    state["session"] = sid
    state["corrections"] = {}
    state["pending_review"] = []
    state["extracted_reports"] = []
    state["grader"] = None
    state["rubric"] = None
    state["rubric_json"] = None
    state["criteria_doc"] = ""
    state["calibration"] = None
    state["grading_status"] = None
    state["approved_ids"] = _load_approved()
    for sub in ("rubrics", "reports", "grading", "uploads"):
        os.makedirs(os.path.join(_session_dir(sid), sub), exist_ok=True)
    rubric_json = rubric_io.load_rubric_json(os.path.join(_session_dir(sid), "rubrics", "rubric_current.json"))
    if rubric_json and rubric_json.get("criteria"):
        state["rubric_json"] = rubric_json
        state["rubric"] = rubric_io.criteria_to_markdown(rubric_json)
    doc_path = os.path.join(_session_dir(sid), "rubrics", "criteria_doc.txt")
    if os.path.exists(doc_path):
        with open(doc_path, "r", encoding="utf-8") as f:
            state["criteria_doc"] = f.read()
    reports_dir = os.path.join(_session_dir(sid), "reports")
    if os.path.isdir(reports_dir):
        for name in sorted(os.listdir(reports_dir)):
            meta_path = os.path.join(reports_dir, name, "meta.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                state["extracted_reports"].append({"status": "ok", "meta": meta, "images": []})
    results_path = os.path.join(_session_dir(sid), "grading", "grading_results.json")
    if os.path.exists(results_path) and state["rubric_json"]:
        llm = LLMClient(state["config"])
        g = Grader(state["rubric_json"], llm_client=llm, config=state["config"],
                   output_dir=os.path.join(_session_dir(sid), "grading"), similarity_scope=sid)
        with open(results_path, "r", encoding="utf-8") as f:
            g.results = json.load(f)
        state["grader"] = g


_idx = _load_sessions()
if not _idx["sessions"]:
    _new_session("默认课程")
else:
    _hydrate_session(_idx["current"] or _idx["sessions"][-1]["id"])


@app.context_processor
def inject_global():
    idx = _load_sessions()
    current = next((s for s in idx["sessions"] if s["id"] == state.get("session")), {})
    return {
        "rubric": state.get("rubric"),
        "reports_count": len(state.get("extracted_reports", [])),
        "graded_count": len(state["grader"].results) if state.get("grader") else 0,
        "total_count": len([r for r in state.get("extracted_reports", []) if r.get("status") == "ok"]),
        "pending_count": len([r for r in state.get("extracted_reports", [])
                              if r.get("status") == "ok" and r["meta"]["filename"]
                              not in ({x["report_id"] for x in state["grader"].results}
                                      if state.get("grader") else set())]),
        "sessions": idx["sessions"],
        "current_session": current,
    }


@app.route("/session/new", methods=["POST"])
def session_new():
    entry = _new_session(request.form.get("name", ""))
    _hydrate_session(entry["id"])
    return redirect(url_for("index"))


@app.route("/session/switch", methods=["POST"])
def session_switch():
    sid = request.form.get("session_id", "")
    idx = _load_sessions()
    if any(s["id"] == sid for s in idx["sessions"]):
        idx["current"] = sid
        _save_sessions(idx)
        _hydrate_session(sid)
    return redirect(request.form.get("next") or url_for("index"))


@app.route("/session/remove", methods=["POST"])
def session_remove():
    sid = request.form.get("session_id", "")
    idx = _load_sessions()
    idx["sessions"] = [s for s in idx["sessions"] if s["id"] != sid]
    if not idx["sessions"]:
        _save_sessions(idx)
        entry = _new_session("默认课程")
        _hydrate_session(entry["id"])
    else:
        if idx["current"] == sid:
            idx["current"] = idx["sessions"][-1]["id"]
        _save_sessions(idx)
        _hydrate_session(idx["current"])
    return redirect(url_for("index"))


@app.route("/")
def index():
    return render_template("index.html")


def _read_doc_text(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        import pymupdf
        doc = pymupdf.open(filepath)
        text = "\n".join(page.get_text("text") for page in doc)
        doc.close()
        return text
    if ext == ".docx":
        from docx import Document
        return "\n".join(p.text for p in Document(filepath).paragraphs)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


@app.route("/upload_criteria", methods=["POST"])
def upload_criteria():
    f = request.files.get("criteria_file")
    if not f:
        return jsonify({"error": "No file uploaded"}), 400
    filepath = os.path.join(_session_sub("uploads"), f.filename)
    f.save(filepath)
    doc_text = _read_doc_text(filepath)
    llm = LLMClient(state["config"])
    gen = RubricGenerator(llm_client=llm, output_dir=_session_sub("rubrics"))
    try:
        rubric_json = gen.generate_structured(doc_text)
    except ValueError as e:
        return render_template("rubric_review.html", rubric_json=state.get("rubric_json"),
                               error=f"Rubric 结构化生成失败：{e}")
    state["criteria_doc"] = doc_text
    state["rubric_json"] = rubric_json
    state["rubric"] = rubric_io.criteria_to_markdown(rubric_json)
    rubric_io.save_rubric_json(rubric_json, os.path.join(_session_dir(), "rubrics", "rubric_current.json"))
    with open(os.path.join(_session_dir(), "rubrics", "rubric_latest.md"), "w", encoding="utf-8") as f:
        f.write(state["rubric"])
    with open(os.path.join(_session_dir(), "rubrics", "criteria_doc.txt"), "w", encoding="utf-8") as f:
        f.write(doc_text)
    return redirect(url_for("rubric_review"))


@app.route("/rubric_review")
def rubric_review():
    return render_template("rubric_review.html", rubric_json=state.get("rubric_json"))


@app.route("/rubric_gen_row", methods=["POST"])
def rubric_gen_row():
    name = (request.json or {}).get("name", "").strip()
    if not name:
        return jsonify({"error": "维度名称必填"}), 400
    llm = LLMClient(state["config"])
    gen = RubricGenerator(llm_client=llm)
    try:
        row = gen.generate_row(state.get("criteria_doc", ""), name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422
    return jsonify(row)


@app.route("/rubric_gen_cell", methods=["POST"])
def rubric_gen_cell():
    data = request.get_json(force=True)
    name = str(data.get("name", "")).strip()
    valid_fields = {"weight", "doc_ref", "A", "B", "C", "D"}
    fields = [f for f in (data.get("fields") or []) if f in valid_fields]
    if not name or not fields:
        return jsonify({"error": "需要维度名称和至少一个待补全字段"}), 400
    llm = LLMClient(state["config"])
    gen = RubricGenerator(llm_client=llm)
    try:
        filled = gen.generate_cells(state.get("criteria_doc", ""), name, data.get("context") or {}, fields)
    except Exception as e:
        return jsonify({"error": f"生成失败：{e}"}), 422
    return jsonify(filled)


@app.route("/rubric_validate", methods=["POST"])
def rubric_validate():
    data = request.get_json(force=True)
    rubric = {"criteria": data.get("criteria", [])}
    warnings = rubric_io.check_vague_and_refs(rubric["criteria"])
    llm = LLMClient(state["config"])
    gen = RubricGenerator(llm_client=llm)
    try:
        warnings += gen.validate_deviation(state.get("criteria_doc", ""), rubric)
    except Exception as e:
        warnings.append({"criterion": "-", "message": f"偏差校验 LLM 调用失败：{e}"})
    return jsonify({"warnings": warnings})


@app.route("/rubric_table_save", methods=["POST"])
def rubric_table_save():
    data = request.get_json(force=True)
    criteria = data.get("criteria", [])
    if not criteria:
        return jsonify({"error": "至少保留一个评分维度"}), 400
    for c in criteria:
        if not str(c.get("name", "")).strip():
            return jsonify({"error": "存在未命名维度，请填写维度名称"}), 400
    warnings = rubric_io.check_vague_and_refs(criteria)
    if warnings and not data.get("force"):
        return jsonify({"warnings": warnings}), 409
    rubric_json = {"criteria": rubric_io.normalize_weights(criteria)}
    state["rubric_json"] = rubric_json
    state["rubric"] = rubric_io.criteria_to_markdown(rubric_json)
    rubric_io.save_rubric_json(rubric_json, os.path.join(_session_dir(), "rubrics", "rubric_current.json"))
    with open(os.path.join(_session_dir(), "rubrics", "rubric_latest.md"), "w", encoding="utf-8") as f:
        f.write(state["rubric"])
    return jsonify({"ok": True})


@app.route("/calibrate_upload", methods=["POST"])
def calibrate_upload():
    report_file = request.files.get("calibration_report")
    if not report_file:
        return jsonify({"error": "No calibration report uploaded"}), 400
    if not state.get("rubric_json"):
        return render_template("rubric_review.html", rubric_json=None,
                               error="请先生成评分细则，再使用校准模式")
    filepath = os.path.join(_session_sub("uploads"), "calibration_" + report_file.filename)
    report_file.save(filepath)
    extractor = ReportExtractor(_session_sub("calibration"), state["config"])
    extraction = extractor._process_single(filepath)
    text_path = os.path.join(extraction["meta"]["output_dir"], "text.md")
    with open(text_path, "r", encoding="utf-8") as f:
        text = f.read()

    llm = LLMClient(state["config"])
    tmp_grader = Grader(state["rubric_json"], llm_client=llm, config=state["config"],
                        similarity_scope=state.get("session"))
    chunks = [c for c in re.split(r"\n\s*\n", text) if c.strip()][:30]
    chunk_entries = [{"id": f"p{i}", "text": c[:300]} for i, c in enumerate(chunks)]
    assignments = tmp_grader.assign_images(chunk_entries)

    state["calibration"] = {"text": text, "chunks": chunks, "assignments": assignments,
                            "meta": extraction["meta"],
                            "filename": extraction["meta"].get("filename", report_file.filename)}
    return redirect(url_for("calibrate_score"))


@app.route("/calibrate_score")
def calibrate_score():
    if not state.get("calibration"):
        return redirect(url_for("rubric_review"))
    return render_template("calibrate_score.html", calib=state["calibration"],
                           rubric_json=state.get("rubric_json"))


@app.route("/rubric_calibrate", methods=["POST"])
def rubric_calibrate():
    calib = state.get("calibration")
    if not calib:
        return redirect(url_for("rubric_review"))
    report_text = calib["text"]

    llm = LLMClient(state["config"])
    gen = RubricGenerator(llm_client=llm)

    teacher_grading = {}
    criteria = state.get("rubric_json", {}).get("criteria", [])
    for c in criteria:
        cname = c.get("name", "")
        lv = request.form.get(f"teacher_level::{cname}")
        if lv in VALID_LEVELS:
            teacher_grading[cname] = {
                "level": lv, "evidence": "",
                "reasoning": request.form.get(f"teacher_reason::{cname}", "").strip(),
            }

    from nodes.grader import GRADING_PROMPT
    prompt = GRADING_PROMPT.format(
        criteria_block=gen._criteria_block(_coerce_rubric(state["rubric_json"]).get("criteria", []))
        if state.get("rubric_json") else "(未配置)",
        report_text=report_text[:8000],
        image_descriptions="Calibration report",
        knowledge_context="",
    )
    ai_grading_text = llm.chat([{"role": "user", "content": prompt}])
    from nodes.grader import _parse_json
    ai_grading = _parse_json(ai_grading_text)

    calibration_result = gen.calibrate(state.get("rubric", ""), report_text, teacher_grading, ai_grading)
    return render_template("calibration_result.html", result=calibration_result, ai_grading=ai_grading)


@app.route("/upload_reports", methods=["POST"])
def upload_reports():
    files = request.files.getlist("report_files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400
    upload_dir = _session_sub("uploads")
    for f in files:
        f.save(os.path.join(upload_dir, f.filename))

    extractor = ReportExtractor(_session_sub("reports"), state["config"])
    results = extractor.extract_all(upload_dir)
    state["extracted_reports"] = results
    return redirect(url_for("reports_list"))


def _approved_path():
    return os.path.join(_session_dir(), "approved.json")


def _load_approved():
    p = _approved_path()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def _save_approved(ids):
    with open(_approved_path(), "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False)


@app.route("/reports_list")
def reports_list():
    graded = {r["report_id"] for r in state["grader"].results
              if r.get("status") == "graded"} if state["grader"] else set()
    return render_template("reports_list.html", reports=state["extracted_reports"],
                           graded_ids=graded, approved_ids=state.get("approved_ids", set()))


@app.route("/report_text/<path:filename>")
def report_text(filename):
    entry = next((r for r in state["extracted_reports"]
                  if r.get("meta", {}).get("filename") == filename), None)
    if not entry:
        return jsonify({"error": "not found"}), 404
    text_path = os.path.join(entry["meta"]["output_dir"], "text.md")
    text = ""
    if os.path.exists(text_path):
        with open(text_path, "r", encoding="utf-8") as f:
            text = f.read()
    chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
    pages = [chunks[i:i + 4] for i in range(0, len(chunks), 4)] or [["（此报告无文本内容）"]]
    return jsonify({"filename": filename, "pages": pages})


@app.route("/report_original/<path:filename>")
def report_original(filename):
    name = os.path.basename(filename)
    root = os.path.dirname(__file__)
    for d in (_session_sub("uploads"), os.path.join(root, "uploads"), os.path.join(root, "test_data")):
        path = os.path.join(d, name)
        if os.path.exists(path):
            return send_file(path)
    return "原文文件不存在", 404


@app.route("/report/<path:filename>")
def report_detail(filename):
    entry = next((r for r in state["extracted_reports"]
                  if r.get("meta", {}).get("filename") == filename), None)
    if not entry or entry.get("status") != "ok":
        return "报告不存在", 404
    text_path = os.path.join(entry["meta"]["output_dir"], "text.md")
    text = ""
    if os.path.exists(text_path):
        with open(text_path, "r", encoding="utf-8") as f:
            text = f.read()
    result = next((r for r in (state["grader"].results if state["grader"] else [])
                   if r["report_id"] == filename), None)
    rubric_json = state.get("rubric_json") or _coerce_rubric(state.get("rubric") or "")
    blocks = _build_dim_blocks(rubric_json, text, result)
    return render_template("report_detail.html", entry=entry, filename=filename,
                           blocks=blocks, result=result, rubric_json=rubric_json)


def _build_dim_blocks(rubric_json, text, result):
    chunks = [c for c in re.split(r"\n\s*\n", text) if c.strip()]
    assignments = (result or {}).get("text_assignments", {})
    img_assign = (result or {}).get("image_assignments", {})
    images = (result or {}).get("images", [])
    scores = ((result or {}).get("grading") or {}).get("scores", {})
    blocks = []
    used_chunks, used_imgs = set(), set()
    for c in rubric_json.get("criteria", []):
        name = c["name"]
        dim_chunks = [chunks[int(aid[1:])] for aid, a in assignments.items()
                      if a.get("criterion") == name and aid.startswith("p") and aid[1:].isdigit() and int(aid[1:]) < len(chunks)]
        used_chunks.update(aid for aid, a in assignments.items() if a.get("criterion") == name)
        dim_imgs = [im for im in images if img_assign.get(im["filename"], {}).get("criterion") == name]
        used_imgs.update(im["filename"] for im in dim_imgs)
        blocks.append({
            "criterion": name, "weight": c.get("weight"), "mechanical": c.get("mechanical"),
            "doc_ref": c.get("doc_ref"), "levels": c.get("levels", {}),
            "chunks": dim_chunks, "images": dim_imgs, "score": scores.get(name),
        })
    blocks.append({
        "criterion": "未挂载内容", "weight": None, "mechanical": False, "doc_ref": "",
        "levels": {},
        "chunks": [chunks[i] for i in range(len(chunks)) if f"p{i}" not in used_chunks],
        "images": [im for im in images if im["filename"] not in used_imgs],
        "score": None,
    })
    return blocks


@app.route("/report_image/<path:filename>/<path:imgname>")
def report_image(filename, imgname):
    entry = next((r for r in state["extracted_reports"]
                  if r.get("meta", {}).get("filename") == filename), None)
    if not entry:
        return "未找到", 404
    return send_file(os.path.join(entry["meta"]["output_dir"], "images", imgname))


def _image_entries_with_ocr(images, ocr_cfg):
    entries = []
    if not images:
        return entries
    try:
        from utils.ocr_engine import OCREngine
        eng = OCREngine.get(ocr_cfg)
    except Exception:
        eng = None
    for im in images:
        text = ""
        if eng is not None:
            try:
                path = os.path.join(im.get("_dir", ""), im["filename"])
                if os.path.exists(path):
                    text = eng.recognize_file(path)
            except Exception:
                text = ""
        entries.append({"id": im["filename"], "text": text or im.get("context", "")})
    return entries


def _grade_one(grader, report_result):
    filename = report_result["meta"]["filename"]
    text_path = os.path.join(report_result["meta"]["output_dir"], "text.md")
    if not os.path.exists(text_path):
        return None
    with open(text_path, "r", encoding="utf-8") as f:
        text = f.read()

    images = report_result.get("images", [])
    img_dir = report_result["meta"]["output_dir"]
    for im in images:
        im["_dir"] = img_dir
    ocr_cfg = state["config"].get("ocr", {})
    image_entries = _image_entries_with_ocr(images, ocr_cfg)
    image_assignments = grader.assign_images(image_entries)

    chunks = [c for c in re.split(r"\n\s*\n", text) if c.strip()][:30]
    chunk_entries = [{"id": f"p{i}", "text": c[:300]} for i, c in enumerate(chunks)]
    text_assignments = grader.assign_images(chunk_entries)

    corrections = state["corrections"].get(filename)
    grade_text = text + (f"\n\n[教师修改意见，本次重评须重点回应] {corrections}" if corrections else "")

    grading_result = grader.grade_single(filename, grade_text)
    if grading_result["result"]["status"] == "graded":
        grading_result["result"]["_report_text"] = text
        grading_result["result"]["images"] = images
        grading_result["result"]["image_assignments"] = image_assignments
        grading_result["result"]["text_assignments"] = text_assignments
    return grading_result


def _spawn_grading(target_fn):
    def work():
        g = state["grader"]
        try:
            targets = target_fn()
            state["grading_status"] = {"phase": "running", "done": 0,
                                       "total": len(targets), "current": ""}
            for i, entry in enumerate(targets):
                if state["grading_status"]["phase"] != "running":
                    return
                state["grading_status"]["current"] = entry["meta"]["filename"]
                res = _grade_one(g, entry)
                state["grading_status"]["done"] = i + 1
                if res is None:
                    continue
                if res.get("needs_review"):
                    state["pending_review"] = res["batch"]
                    state["grading_status"]["phase"] = "needs_review"
                    return
            g.export_results()
            g.export_excel()
            state["grading_status"]["phase"] = "done"
        except Exception as e:
            state["grading_status"] = {"phase": "error", "message": str(e), "done": 0, "total": 0}

    threading.Thread(target=work, daemon=True).start()


def _ungraded_reports():
    graded = {r["report_id"] for r in state["grader"].results}
    return [r for r in state["extracted_reports"]
            if r.get("status") == "ok" and r["meta"]["filename"] not in graded]


@app.route("/start_grading")
def start_grading():
    if not state.get("rubric_json") and not state.get("rubric"):
        return jsonify({"error": "No rubric defined"}), 400
    with state["grading_lock"]:
        if state.get("grading_status", {}) and state["grading_status"].get("phase") == "running":
            return redirect(url_for("grading_progress"))
        remaining = _ungraded_reports()
        if not remaining:
            return redirect(url_for("grading_done"))
        prev_results = state["grader"].results if state["grader"] else []
        llm = LLMClient(state["config"])
        state["grader"] = Grader(state.get("rubric_json") or state["rubric"], llm_client=llm,
                                 config=state["config"], output_dir=_session_sub("grading"),
                                 similarity_scope=state.get("session"))
        state["grader"].results = prev_results
        state["grading_status"] = {"phase": "running", "done": 0, "total": 0, "current": ""}
        _spawn_grading(lambda: remaining)
    return redirect(url_for("grading_progress"))


@app.route("/grading_progress")
def grading_progress():
    return render_template("grading_progress.html", status=state.get("grading_status") or {})


@app.route("/grading_status")
def grading_status():
    return jsonify(state.get("grading_status") or {"phase": "idle"})


@app.route("/regrade/<path:filename>", methods=["POST"])
def regrade(filename):
    if not state["grader"]:
        return jsonify({"error": "No grader"}), 400
    with state["grading_lock"]:
        if state.get("grading_status", {}) and state["grading_status"].get("phase") == "running":
            return redirect(url_for("grading_progress"))
        state["grader"].rubric = _coerce_rubric(state.get("rubric_json") or state.get("rubric") or "")
        entry = next((r for r in state["extracted_reports"]
                      if r.get("meta", {}).get("filename") == filename), None)
        if not entry:
            return jsonify({"error": "报告不存在"}), 404
        state["grader"].results = [r for r in state["grader"].results if r["report_id"] != filename]
        state["grader"].pending_review = [r for r in state["grader"].pending_review if r["report_id"] != filename]
        entry["status"] = "ok"

        def targets():
            return [entry]
        state["grading_status"] = {"phase": "running", "done": 0, "total": 1, "current": filename}
        _spawn_grading(targets)
    return redirect(url_for("grading_progress"))


def _apply_teacher_levels(result, form, prefix_level, prefix_reason=""):
    if result.get("status") != "graded" or "grading" not in result:
        return False
    scores = result["grading"].get("scores", {})
    for criterion in list(scores):
        v = form.get(f"{prefix_level}{criterion}")
        if v in VALID_LEVELS and v != scores[criterion].get("level"):
            scores[criterion]["level"] = v
            scores[criterion]["teacher_adjusted"] = True
        if prefix_reason:
            reason = form.get(f"{prefix_reason}{criterion}", "").strip()
            if reason:
                scores[criterion]["teacher_reasoning"] = reason
    rubric_json = state.get("rubric_json") or _coerce_rubric(state.get("rubric") or "")
    result["grading"]["subtotals"] = rubric_io.compute_subtotals(scores, rubric_json)
    return True


@app.route("/review_batch")
def review_batch():
    return render_template("review_batch.html", batch=state.get("pending_review", []),
                           rubric_json=state.get("rubric_json"))


@app.route("/approve_batch", methods=["POST"])
def approve_batch():
    if state["grader"]:
        approved_ids = set()
        for r in state["pending_review"]:
            _apply_teacher_levels(r, request.form, f"adj::{r['report_id']}::", f"reason::{r['report_id']}::")
            if r.get("status") == "graded":
                approved_ids.add(r["report_id"])
        state["grader"].approve_batch()
        state["pending_review"] = []
        state["approved_ids"] = state.get("approved_ids", set()) | approved_ids
        _save_approved(state["approved_ids"])
        if not _ungraded_reports():
            state["grader"].export_results()
            state["grader"].export_excel()
            state["grading_status"] = {"phase": "done", "done": len(state["grader"].results),
                                       "total": len(state["grader"].results), "current": ""}
    return redirect(url_for("continue_grading"))


@app.route("/reject_batch", methods=["POST"])
def reject_batch():
    corrections = request.form.get("corrections", "")
    rejected_ids = []
    if state["grader"]:
        rejected_ids = [r["report_id"] for r in state["pending_review"]]
        state["grader"].reject_batch(corrections)
    for rid in rejected_ids:
        state["corrections"][rid] = corrections
    for r in state.get("extracted_reports", []):
        if r.get("meta", {}).get("filename") in rejected_ids:
            r["status"] = "pending_regrade"
    return redirect(url_for("reports_list"))


@app.route("/continue_grading")
def continue_grading():
    if not state["grader"]:
        return redirect(url_for("grading_done"))
    with state["grading_lock"]:
        if state.get("grading_status", {}) and state["grading_status"].get("phase") == "running":
            return redirect(url_for("grading_progress"))
        remaining = _ungraded_reports()
        if not remaining:
            return redirect(url_for("grading_done"))
        state["grading_status"] = {"phase": "running", "done": 0,
                                   "total": len(remaining), "current": ""}
        _spawn_grading(lambda: remaining)
    return redirect(url_for("grading_progress"))


@app.route("/update_scores", methods=["POST"])
def update_scores():
    if not state["grader"]:
        return jsonify({"error": "No grading results"}), 400
    report_id = request.form.get("report_id")
    updated = False
    for r in state["grader"].results:
        if r["report_id"] == report_id:
            updated = _apply_teacher_levels(r, request.form, "level::", "reason::") or updated
    if updated:
        state["grader"].export_results()
        state["grader"].export_excel()
    return redirect(url_for("grading_done"))


@app.route("/approve_report/<path:filename>", methods=["POST"])
def approve_report(filename):
    g = state["grader"]
    if not g:
        return jsonify({"error": "No grading results"}), 400
    if filename not in state.get("approved_ids", set()):
        result = next((r for r in g.results
                       if r["report_id"] == filename and r.get("status") == "graded"), None)
        if not result:
            return jsonify({"error": "报告未评分或状态异常"}), 400
        text = result.get("_report_text", "")
        if not text:
            entry = next((r for r in state["extracted_reports"]
                          if r.get("meta", {}).get("filename") == filename), None)
            if entry:
                p = os.path.join(entry["meta"]["output_dir"], "text.md")
                if os.path.exists(p):
                    with open(p, "r", encoding="utf-8") as f:
                        text = f.read()
        from nodes.grader import anonymize_text
        anonymized, _ = anonymize_text(text)
        scrubbed_json, _ = anonymize_text(json.dumps(result["grading"], ensure_ascii=False))
        try:
            scrubbed = json.loads(scrubbed_json)
        except json.JSONDecodeError:
            scrubbed = result["grading"]
        g.kb.add_case(f"case_{filename}", anonymized, scrubbed)
        state["approved_ids"] = state.get("approved_ids", set()) | {filename}
        _save_approved(state["approved_ids"])
        g.export_results()
    return redirect(url_for("grading_done"))


@app.route("/grading_done")
def grading_done():
    results = state["grader"].results if state["grader"] else []
    approved_ids = state.get("approved_ids", set())
    counts = {
        "all": len(results),
        "injection": len([r for r in results if r.get("status") == "flagged_injection"]),
        "plagiarism": len([r for r in results if r.get("similarity_warnings")]),
        "unapproved": len([r for r in results if r["report_id"] not in approved_ids]),
    }
    if state["grader"]:
        excel_path = state["grader"].export_excel()
        json_path = state["grader"].export_results()
        return render_template("grading_done.html",
                               results=results,
                               counts=counts,
                               approved_ids=approved_ids,
                               excel_path=excel_path,
                               json_path=json_path,
                               rubric_json=state.get("rubric_json"))
    return render_template("grading_done.html", results=[], counts=counts,
                           approved_ids=approved_ids, excel_path="", json_path="",
                           rubric_json=state.get("rubric_json"))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    cfg = state["config"]
    if request.method == "POST":
        openai = cfg.setdefault("llm", {}).setdefault("openai", {})
        openai["base_url"] = request.form.get("base_url", openai.get("base_url", ""))
        openai["model"] = request.form.get("model", openai.get("model", ""))
        api_key = request.form.get("api_key", "").strip()
        if api_key:
            openai["api_key"] = api_key
        openai["max_tokens"] = int(request.form.get("max_tokens") or openai.get("max_tokens") or 2048)
        ocr = cfg.setdefault("ocr", {})
        ocr["backend"] = request.form.get("ocr_backend", ocr.get("backend", "paddleocr"))
        api = ocr.setdefault("api", {})
        api["api_url"] = request.form.get("ocr_api_url", api.get("api_url", ""))
        ocr_key = request.form.get("ocr_api_key", "").strip()
        if ocr_key:
            api["api_key"] = ocr_key
        api["api_model"] = request.form.get("ocr_api_model", api.get("api_model", ""))
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
        state["config"] = cfg
        return render_template("settings.html", cfg=cfg, saved=True)
    return render_template("settings.html", cfg=cfg, saved=False)


@app.route("/download/<path:filename>")
def download(filename):
    return send_file(os.path.join(_session_dir(), filename), as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
