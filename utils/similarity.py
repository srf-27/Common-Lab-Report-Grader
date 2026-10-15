import numpy as np
import chromadb


class SimilarityChecker:
    def __init__(self, chroma_client, collection_name="report_similarity"):
        self.client = chroma_client
        self.collection = chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def check_against_all(self, report_id, text):
        if self.collection.count() == 0:
            return []
        results = self.collection.query(query_texts=[text], n_results=min(self.collection.count(), 10))
        warnings = []
        for i, doc_text in enumerate(results["documents"][0]):
            distance = results["distances"][0][i]
            similarity = 1 - distance
            if similarity >= 0.70:
                warnings.append({
                    "matched_id": results["ids"][0][i],
                    "similarity": round(similarity, 4),
                    "level": "rejected" if similarity >= 0.95 else "warning",
                })
        return warnings

    def add_report(self, report_id, text):
        self.collection.add(documents=[text], ids=[report_id])
