"""storage 统一持久化入口：文件后端往返、无 dsn 保持文件、坏 dsn 静默降级。

有真实 PostgreSQL 时可跑 PG 往返：设置环境变量 ERG_PG_TEST_DSN（如
postgresql://user:pass@localhost:5432/erg_test），未设置则跳过该部分。
"""

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))

from experiment_report_grader import storage            # noqa: E402
from experiment_report_grader.web import state as state_mod  # noqa: E402


def _with_tmp_sessions(fn):
    tmp = tempfile.mkdtemp(prefix="erg_store_")
    real_output, real_sessions = state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR
    try:
        state_mod.OUTPUT_FOLDER = os.path.join(tmp, "output")
        state_mod.SESSIONS_DIR = os.path.join(state_mod.OUTPUT_FOLDER, "sessions")
        os.makedirs(state_mod.SESSIONS_DIR, exist_ok=True)
        fn(state_mod.SESSIONS_DIR)
    finally:
        state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR = real_output, real_sessions
        shutil.rmtree(tmp, ignore_errors=True)


def test_file_backend_roundtrip():
    def body(sessions):
        assert storage.backend_name() == "file"
        path = os.path.join(sessions, "s1", "grading", "grading_results.json")
        data = [{"report_id": "r1", "status": "graded"}]
        storage.write_json(path, data, indent=2)
        assert storage.read_json(path, None) == data
        assert storage.exists(path)
        text_path = os.path.join(sessions, "s1", "reports", "r1", "text.md")
        storage.write_text(text_path, "报告正文，含中文")
        assert storage.read_text(text_path) == "报告正文，含中文"
        assert storage.read_json(os.path.join(sessions, "missing.json"), "dft") == "dft"
        storage.remove(path)
        assert not storage.exists(path)
        # sessions 目录外的路径不受影响，直接走文件
        outside = os.path.join(sessions, "..", "outside.json")
        storage.write_json(outside, {"a": 1})
        assert storage.read_json(outside) == {"a": 1}

    _with_tmp_sessions(body)


def test_configure_without_dsn_stays_file():
    saved = (storage._backend, storage._pg_conn, storage._pg_broken_reason)
    try:
        os.environ.pop("ERG_PG_DSN", None)
        storage._backend, storage._pg_conn, storage._pg_broken_reason = "file", None, ""
        storage.configure({"storage": {"postgres": {"dsn": ""}}})
        assert storage.backend_name() == "file"
    finally:
        storage._backend, storage._pg_conn, storage._pg_broken_reason = saved


def test_configure_bad_dsn_degrades_to_file():
    saved = (storage._backend, storage._pg_conn, storage._pg_broken_reason)
    saved_env = os.environ.pop("ERG_PG_DSN", None)
    try:
        storage._backend, storage._pg_conn, storage._pg_broken_reason = "file", None, ""
        # 指向必然连不上的地址；psycopg 未安装时同样应降级而不是抛错
        storage.configure({"storage": {"postgres": {
            "dsn": "postgresql://erg:nopass@127.0.0.1:1/erg_none"}}})
        assert storage.backend_name() == "file"
        # 降级后读写仍走文件
        def body(sessions):
            path = os.path.join(sessions, "s1", "x.json")
            storage.write_json(path, [1, 2])
            assert storage.read_json(path) == [1, 2]

        _with_tmp_sessions(body)
    finally:
        storage._backend, storage._pg_conn, storage._pg_broken_reason = saved
        if saved_env is not None:
            os.environ["ERG_PG_DSN"] = saved_env


def test_pg_roundtrip_if_available():
    dsn = os.environ.get("ERG_PG_TEST_DSN", "")
    if not dsn:
        print("  (skip: 未设置 ERG_PG_TEST_DSN，跳过 PostgreSQL 真实往返)")
        return
    saved = (storage._backend, storage._pg_conn, storage._pg_broken_reason)
    try:
        os.environ["ERG_PG_DSN"] = dsn
        storage._backend, storage._pg_conn, storage._pg_broken_reason = "file", None, ""

        def body(sessions):
            storage.configure({})
            if storage.backend_name() != "pg":
                print("  (skip: 连不上测试库，已降级)")
                return
            path = os.path.join(sessions, "s_pg_test", "grading", "r.json")
            data = {"k": "中文值", "n": [1, 2, 3]}
            storage.write_json(path, data)
            assert storage.read_json(path, None) == data
            assert storage.exists(path)
            text = os.path.join(sessions, "s_pg_test", "reports", "a", "text.md")
            storage.write_text(text, "正文内容")
            assert storage.read_text(text) == "正文内容"
            # PG 模式下文件作热镜像：直读磁盘的调用方（如 upload.save 的原件）仍一致
            with open(path, encoding="utf-8") as f:
                import json as _json
                assert _json.load(f) == data
            storage.remove(path)
            assert not storage.exists(path)
            assert not os.path.exists(path)

        _with_tmp_sessions(body)
    finally:
        storage._backend, storage._pg_conn, storage._pg_broken_reason = saved
        os.environ.pop("ERG_PG_DSN", None)
