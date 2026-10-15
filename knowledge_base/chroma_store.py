import os
import json
import chromadb


class KnowledgeBase:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "db")
        os.makedirs(db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name="grading_cases",
            metadata={"hnsw:space": "cosine"}
        )

    def add_case(self, case_id, text, grading_result, rubric_version="v1"):
        metadata = {
            "rubric_version": rubric_version,
            "grading_json": json.dumps(grading_result, ensure_ascii=False)[:5000],
        }
        self.collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[case_id],
        )

    def search_similar(self, text, n_results=3):
        if self.collection.count() == 0:
            return []
        n = min(n_results, self.collection.count())
        results = self.collection.query(query_texts=[text], n_results=n)
        cases = []
        for i in range(len(results["ids"][0])):
            cases.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
        return cases

    def count(self):
        return self.collection.count()

    def delete_case(self, case_id):
        self.collection.delete(ids=[case_id])
