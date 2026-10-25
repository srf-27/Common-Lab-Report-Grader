"""markitdown 兜底解析的边界：插件缺席 / 开关关闭 / 本地解析失败。"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.mcp import store as mcp_store
from experiment_report_grader.nodes.report_extractor import ReportExtractor


def _html(tmp, name="李四_实验报告.html"):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("<html><body><h1>实验报告</h1><p>用逐差法处理，不确定度 0.004m。</p></body></html>")
    return path


def _with_empty_registry():
    """临时把插件注册表指到空文件，模拟未安装 markitdown 的环境。"""
    tmp = tempfile.mkdtemp(prefix="erg_md_")
    real = mcp_store.CONFIG_PATH
    empty = os.path.join(tmp, "mcp.yaml")
    with open(empty, "w", encoding="utf-8") as f:
        f.write("servers: {}\n")
    mcp_store.CONFIG_PATH = empty
    return tmp, real


def test_fallback_absent_plugin_keeps_original_behavior():
    tmp, real = _with_empty_registry()
    try:
        ex = ReportExtractor(os.path.join(tmp, "reports"), {})
        r = ex._process_single(_html(tmp))
        assert r["status"] == "skipped", "插件缺席时 Unsupported format 行为与原来一致"
        assert "markitdown" in r["reason"]
    finally:
        mcp_store.CONFIG_PATH = real


def test_fallback_disabled_by_switch():
    tmp, real = _with_empty_registry()
    try:
        ex = ReportExtractor(os.path.join(tmp, "reports"),
                             {"extraction": {"markitdown_fallback": False}})
        r = ex._process_single(_html(tmp))
        assert r["status"] == "skipped", "开关关闭 → 完全走原路径"
    finally:
        mcp_store.CONFIG_PATH = real


def test_local_parse_error_falls_back_then_reports_error():
    """本地支持格式的解析失败：先试 markitdown，仍不可用则返回原错误。"""
    tmp, real = _with_empty_registry()
    try:
        broken_pdf = os.path.join(tmp, "坏文件.pdf")
        with open(broken_pdf, "wb") as f:
            f.write(b"not a pdf at all")  # 无效 PDF 头
        ex = ReportExtractor(os.path.join(tmp, "reports"), {})
        r = ex._process_single(broken_pdf)
        assert r["status"] == "error", "本地失败且无兜底 → error（不再是无声 skipped）"
    finally:
        mcp_store.CONFIG_PATH = real


def test_local_formats_not_routed_to_markitdown():
    """本地解析器支持的格式（docx/md）不走兜底；正常路径不受影响。"""
    tmp, real = _with_empty_registry()
    try:
        md = os.path.join(tmp, "王五_笔记.md")
        with open(md, "w", encoding="utf-8") as f:
            f.write("# 实验报告\n\n不确定度 0.01。")
        ex = ReportExtractor(os.path.join(tmp, "reports"), {})
        r = ex._process_single(md)
        assert r["status"] == "ok" and not r["meta"].get("markitdown")
    finally:
        mcp_store.CONFIG_PATH = real


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("test_markitdown_fallback ok")
