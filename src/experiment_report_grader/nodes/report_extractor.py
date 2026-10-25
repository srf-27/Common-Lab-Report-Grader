import os
import pathlib
from datetime import datetime
from .. import storage
from ..utils.file_parser import (
    detect_archive_type, extract_archive, extract_pdf, extract_docx, extract_markdown,
    extract_doc, collect_report_files, MARKITDOWN_EXTENSIONS
)
from ..utils.ocr_engine import OCREngine


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

    def _markitdown_text(self, filepath):
        """markitdown MCP 兜底：本地解析不支持或失败时把文件转成 Markdown。

        插件未注册、进程不存在、转换失败 → 返回 None（调用方回退原有错误路径），
        未安装 markitdown 的环境行为与原来完全一致。
        """
        if not ((self.config or {}).get("extraction") or {}).get("markitdown_fallback", True):
            return None
        try:
            from ..mcp import client as mcp_client
            from ..mcp import store as mcp_store
            server = mcp_store.load_servers().get("markitdown")
            if not server:
                return None
            client = mcp_client.MCPClient(server)
            try:
                result = client.call_tool(
                    "convert_to_markdown",
                    {"uri": pathlib.Path(filepath).resolve().as_uri()})
            finally:
                client.close()
            return mcp_client._text_of(result).strip() or None
        except Exception:
            return None

    def _process_single(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        basename = os.path.splitext(os.path.basename(filepath))[0]
        output_dir = os.path.join(self.output_base, basename)

        meta, images, local_error = None, None, ""
        try:
            if detect_archive_type(filepath) and ext not in (".docx", ".doc"):
                return self._process_archive(filepath, output_dir)
            if ext == ".pdf":
                meta, images = extract_pdf(filepath, output_dir, ocr_engine=self._get_ocr())
            elif ext == ".docx":
                meta, images = extract_docx(filepath, output_dir)
            elif ext == ".doc":
                meta, images = extract_doc(filepath, output_dir)
            elif ext == ".md":
                meta, images = extract_markdown(filepath, output_dir)
            elif ext not in MARKITDOWN_EXTENSIONS:
                return {"status": "skipped", "file": filepath,
                        "reason": f"Unsupported format: {ext}"}
        except Exception as e:
            local_error = str(e)  # 本地解析失败 → 尝试 markitdown 兜底

        if meta is None:
            # 本地不支持或失败：markitdown MCP 兜底；不可用时按原行为返回 skipped/error
            text = self._markitdown_text(filepath)
            if text:
                os.makedirs(output_dir, exist_ok=True)
                storage.write_text(os.path.join(output_dir, "text.md"), text)
                md_meta = {
                    "filename": os.path.basename(filepath),
                    "extract_time": datetime.now().isoformat(),
                    "output_dir": output_dir,
                    "markitdown": True,
                    "source": "markitdown-mcp",
                }
                storage.write_json(os.path.join(output_dir, "meta.json"), md_meta, indent=2)
                return {"status": "ok", "file": filepath, "meta": md_meta, "images": []}
            if local_error:
                return {"status": "error", "file": filepath, "reason": local_error}
            return {"status": "skipped", "file": filepath,
                    "reason": f"Unsupported format: {ext}（markitdown 插件未启用或转换失败）"}

        meta["extract_time"] = datetime.now().isoformat()
        meta["output_dir"] = output_dir
        storage.write_json(os.path.join(output_dir, "meta.json"), meta, indent=2)
        return {"status": "ok", "file": filepath, "meta": meta, "images": images}

    def _process_archive(self, filepath, dest_dir):
        extract_archive(filepath, dest_dir)
        extracted_files = collect_report_files(dest_dir)
        sub_results = []
        for f in extracted_files:
            sub_results.append(self._process_single(f))
        return {"status": "archive", "file": filepath, "extracted": sub_results}
