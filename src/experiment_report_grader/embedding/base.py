"""checked"""
"""向量库抽象基类：子类实现本地（local）与 API（api）两种接入方式。"""

from abc import ABC, abstractmethod


class VectorStoreBase(ABC):
    """向量库统一接口，需要具体实现"""

    @abstractmethod
    def __init__(self, config=None, session_dir=None):
        """config 取 vector_store 配置段，session_dir 用于按会话隔离库/集合。"""

    @classmethod
    @abstractmethod
    def local(cls, path, **kwargs):
        """打开本地库，返回底层客户端。"""

    @classmethod
    @abstractmethod
    def api(cls, **kwargs):
        """连接远端/云服务，返回底层客户端。"""

    @abstractmethod
    def add(self, ids, documents, metadatas=None):
        """写入文档。"""

    @abstractmethod
    def query(self, text, n_results=5):
        """按文本检索，返回 ids/documents/metadatas/distances 四个并列列表。"""

    @abstractmethod
    def count(self):
        """返回库中文档数。"""

    @abstractmethod
    def delete(self, ids):
        """按 id 删除文档。"""
