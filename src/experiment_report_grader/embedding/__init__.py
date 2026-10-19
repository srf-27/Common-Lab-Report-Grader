
"""向量库模块：本地库与远端 Chroma Server 统一入口，并提供嵌入函数工厂。"""

from .base import VectorStoreBase
from .chroma import Chroma


def create_embedding_function(cfg=None):
    """嵌入函数工厂：default 退化为向量库内置嵌入（返回 None，交给具体实现）。"""
    cfg = cfg or {}
    backend = (cfg.get("backend") or "default").lower()
    if backend == "default":
        return None
    if backend == "openai":
        from chromadb.utils import embedding_functions
        oa = cfg.get("openai") or {}
        return embedding_functions.OpenAIEmbeddingFunction(
            api_key=oa.get("api_key") or None,
            model_name=oa.get("model") or "text-embedding-3-small",
            api_base=oa.get("base_url") or None)
    raise ValueError(f"暂不支持的嵌入后端: {backend}")


__all__ = ["VectorStoreBase", "Chroma", "create_embedding_function"]
