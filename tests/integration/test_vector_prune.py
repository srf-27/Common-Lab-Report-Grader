"""删掉维度后，向量库里不能留下同名 collection。"""
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import experiment_report_grader.app as app_mod
from experiment_report_grader.embedding import Chroma
from experiment_report_grader.web import state as state_mod
from experiment_report_grader.web.state import state


def _collection_name(dimension):
    return "dim_" + hashlib.sha1(dimension.encode("utf-8")).hexdigest()[:12]


def test_deleted_dimension_removes_collection():
    tmp = tempfile.mkdtemp(prefix="erg_prune_")
    real_output, real_sessions = state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR
    real_config = state.get("config")
    try:
        state_mod.OUTPUT_FOLDER = tmp
        state_mod.SESSIONS_DIR = str(Path(tmp) / "sessions")
        Path(state_mod.SESSIONS_DIR).mkdir(parents=True)
        state_mod.hydrate_session(state_mod.new_session("向量清理")["id"])
        state["config"] = {"vector_store": {"chroma": {"mode": "local"}}}

        store = Chroma(config=state["config"]["vector_store"],
                       session_dir=state_mod.session_dir(), create=True)
        for dimension in ("保留维度", "删掉维度"):
            collection = store.client.get_or_create_collection(
                _collection_name(dimension), metadata={"dimension": dimension})
            collection.add(ids=[dimension], documents=[f"{dimension}正文"])

        app_mod._sync_dimension_collections(["保留维度", "新维度"])

        remaining = {collection.metadata.get("dimension")
                     for collection in store.client.list_collections()
                     if collection.name.startswith("dim_")}
        assert remaining == {"保留维度", "新维度"}
    finally:
        state["config"] = real_config
        state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR = real_output, real_sessions
        state_mod.hydrate_session(state_mod.load_sessions()["current"])
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_deleted_dimension_removes_collection()
    print("vector prune ok")


def test_confirm_creates_dimension_collections():
    tmp = tempfile.mkdtemp(prefix="erg_confirm_")
    real_output, real_sessions = state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR
    real_config = state.get("config")
    try:
        state_mod.OUTPUT_FOLDER = tmp
        state_mod.SESSIONS_DIR = str(Path(tmp) / "sessions")
        Path(state_mod.SESSIONS_DIR).mkdir(parents=True)
        state_mod.hydrate_session(state_mod.new_session("确认建库")["id"])
        state["config"] = {"vector_store": {"chroma": {"mode": "local"}}}
        state["rubric_json"] = {"criteria": [
            {"name": "维度甲", "weight": 50, "levels": {}},
            {"name": "维度乙", "weight": 50, "levels": {}},
        ]}
        client = app_mod.app.test_client()
        assert client.post("/pilot/confirm").status_code == 200

        store = Chroma(config=state["config"]["vector_store"],
                       session_dir=state_mod.session_dir(), create=False)
        labels = {collection.metadata.get("dimension")
                  for collection in store.client.list_collections()
                  if collection.name.startswith("dim_")}
        assert labels == {"维度甲", "维度乙"}
    finally:
        state["config"] = real_config
        state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR = real_output, real_sessions
        state_mod.hydrate_session(state_mod.load_sessions()["current"])
        shutil.rmtree(tmp, ignore_errors=True)


def test_clear_vector_store_and_running_guard():
    tmp = tempfile.mkdtemp(prefix="erg_clear_")
    real_output, real_sessions = state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR
    real_config = state.get("config")
    try:
        state_mod.OUTPUT_FOLDER = tmp
        state_mod.SESSIONS_DIR = str(Path(tmp) / "sessions")
        Path(state_mod.SESSIONS_DIR).mkdir(parents=True)
        state_mod.hydrate_session(state_mod.new_session("清空向量库")["id"])
        state["config"] = {"vector_store": {"chroma": {"mode": "local"}}}
        store = Chroma(config=state["config"]["vector_store"],
                       session_dir=state_mod.session_dir(), create=True)
        store.client.get_or_create_collection("grading_cases")
        store.client.get_or_create_collection(
            _collection_name("维度甲"), metadata={"dimension": "维度甲"})
        client = app_mod.app.test_client()

        state["grading_status"] = {"phase": "running"}
        assert client.post("/api/vector/clear").status_code == 409
        state["grading_status"] = None

        result = client.post("/api/vector/clear").get_json()
        assert result["ok"] is True and result["deleted"] == 2
        assert store.client.list_collections() == []
    finally:
        state["config"] = real_config
        state["grading_status"] = None
        state_mod.OUTPUT_FOLDER, state_mod.SESSIONS_DIR = real_output, real_sessions
        state_mod.hydrate_session(state_mod.load_sessions()["current"])
        shutil.rmtree(tmp, ignore_errors=True)
