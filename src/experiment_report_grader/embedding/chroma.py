
import os

from .base import VectorStoreBase


class Chroma(VectorStoreBase):
    """Chroma 向量库：本地持久化（local）或远端 Chroma Server（cloud）。"""

    def __init__(self, config=None, session_dir=None, create=True):
        from . import create_embedding_function  # 包级工厂，避免与 __init__ 循环导入
        config = config or {}
        cfg = config.get("chroma") or {}
        embedding_function = create_embedding_function(config.get("embedding"))
        if (cfg.get("mode") or "local").lower() == "cloud":
            self.client = self.api(**cfg)
            name = ("grading_cases_" + os.path.basename(session_dir)
                    if session_dir else "grading_cases")
        else:
            db_path = (os.path.join(session_dir, "kb_db") if session_dir
                       else os.path.join(os.path.dirname(__file__), "db"))
            os.makedirs(db_path, exist_ok=True)
            self.client = self.local(db_path)
            name = "grading_cases"
        if create:
            self.collection = self.client.get_or_create_collection(
                name=name, metadata={"hnsw:space": "cosine"},
                embedding_function=embedding_function)
        else:
            # 只读管理页：不要因为打开页面就创建空 collection
            try:
                self.collection = self.client.get_collection(
                    name=name, embedding_function=embedding_function)
            except Exception:
                self.collection = None

    @classmethod
    def local(cls, path):
        import chromadb
        return chromadb.PersistentClient(path=path)

    @classmethod
    def api(cls, host=None, port=8000, ssl=False, token=None, **_):
        import chromadb
        headers = {"Authorization": f"Bearer {token}"} if token else None
        return chromadb.HttpClient(
            host=host or "localhost", port=int(port or 8000),
            ssl=bool(ssl), headers=headers)

    def add(self, ids, documents, metadatas=None):
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def query(self, text, n_results=5):
        if self.collection.count() == 0:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        return self.collection.query(query_texts=[text], n_results=n_results)

    def count(self):
        return self.collection.count()

    def delete(self, ids):
        self.collection.delete(ids=ids)
