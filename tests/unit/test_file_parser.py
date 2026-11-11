"""解压上限与路径校验：压缩包不能打满磁盘，也不能写出 dest_dir 之外。"""
import io
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from experiment_report_grader.utils import file_parser


def _zip(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, payload in entries:
            zf.writestr(name, payload)
    buffer.seek(0)
    return buffer


def _write(tmp, buffer, name="包.zip"):
    path = Path(tmp) / name
    path.write_bytes(buffer.getvalue())
    return str(path)


def test_normal_zip_extracts():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        dest = str(Path(tmp) / "out")
        path = _write(tmp, _zip([("a.txt", "甲"), ("子目录/b.txt", "乙")]))
        assert file_parser.extract_archive(path, dest) == dest
        assert (Path(dest) / "子目录" / "b.txt").read_text(encoding="utf-8") == "乙"


def test_too_many_entries_rejected():
    original = file_parser.ARCHIVE_MAX_ENTRIES
    file_parser.ARCHIVE_MAX_ENTRIES = 1
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = _write(tmp, _zip([("a.txt", "1"), ("b.txt", "2")]))
            try:
                file_parser.extract_archive(path, str(Path(tmp) / "out"))
                raise AssertionError("超限压缩包应被拒绝")
            except ValueError as e:
                assert "超过上限 1" in str(e), e
            assert not (Path(tmp) / "out" / "a.txt").exists(), "拒绝后不应留下解压文件"
    finally:
        file_parser.ARCHIVE_MAX_ENTRIES = original


def test_oversized_entry_rejected():
    original = file_parser.ARCHIVE_MAX_TOTAL_BYTES
    file_parser.ARCHIVE_MAX_TOTAL_BYTES = 10
    try:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = _write(tmp, _zip([("big.txt", "x" * 100)]))
            try:
                file_parser.extract_archive(path, str(Path(tmp) / "out"))
                raise AssertionError("解压后超体积应被拒绝")
            except ValueError as e:
                assert "超过上限" in str(e), e
    finally:
        file_parser.ARCHIVE_MAX_TOTAL_BYTES = original


def test_traversal_entry_rejected():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = _write(tmp, _zip([("../逃逸.txt", "恶意")]))
        try:
            file_parser.extract_archive(path, str(Path(tmp) / "out"))
            raise AssertionError("越界路径应被拒绝")
        except ValueError as e:
            assert "越界路径" in str(e), e
        assert not (Path(tmp) / "逃逸.txt").exists()
