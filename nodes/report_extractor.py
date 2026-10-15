import os
import json
from datetime import datetime
from utils.file_parser import (
    detect_archive_type, extract_archive, extract_pdf, extract_docx,
    collect_report_files
)
from utils.ocr_engine import OCREngine


class ReportExtractor:
    def __init__(self, output_base, config=None):
        self.output_base = output_base
        self.config = config or {}
        self.ocr_engine = None
        os.makedirs(output_base, exist_ok=True)

    def _get_ocr(self):
        if self.ocr_engine is None:
            OCREngine.reset()
            self.ocr_engine = OCREngine.get(self.config.get("ocr", {}))
        return self.ocr_engine

    def extract_all(self, input_path):
        results = []
        if os.path.isfile(input_path):
            results.append(self._process_single(input_path))
        elif os.path.isdir(input_path):
            for f in collect_report_files(input_path):
                results.append(self._process_single(f))
        return results

    def _process_single(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        basename = os.path.splitext(os.path.basename(filepath))[0]
        output_dir = os.path.join(self.output_base, basename)

        archive_type = detect_archive_type(filepath)
        if archive_type:
            return self._process_archive(filepath, output_dir)

        if ext == ".pdf":
            ocr = self._get_ocr()
            meta, images = extract_pdf(filepath, output_dir, ocr_engine=ocr)
        elif ext == ".docx":
            meta, images = extract_docx(filepath, output_dir)
        else:
            return {"status": "skipped", "file": filepath, "reason": f"Unsupported format: {ext}"}

        meta["extract_time"] = datetime.now().isoformat()
        meta["output_dir"] = output_dir
        with open(os.path.join(output_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "file": filepath, "meta": meta, "images": images}

    def _process_archive(self, filepath, dest_dir):
        extract_archive(filepath, dest_dir)
        extracted_files = collect_report_files(dest_dir)
        sub_results = []
        for f in extracted_files:
            sub_results.append(self._process_single(f))
        return {"status": "archive", "file": filepath, "extracted": sub_results}
