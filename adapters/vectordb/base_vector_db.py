from abc import ABC, abstractmethod
from typing import Dict, List, Any


class BaseVectorDBAdapter(ABC):

    _CODEBASE_PATH = '.\\'
    def __init__(self,config = Dict[str,Any], codebase_path=None):
        self.config = config
        self.codebase_path = codebase_path or self._CODEBASE_PATH
        
    @abstractmethod
    def create_dense_search_request(self, query_text: str, top_k: int) -> Any:
        """创建稠密向量搜索请求"""
        pass
    
    @abstractmethod
    def create_sparse_search_request(self, query_text: str, top_k: int) -> Any:
        """创建稀疏向量搜索请求"""
        pass

    @abstractmethod
    def search(self, requests: List, top_k: int,reranker = None) -> list:
        pass

    @abstractmethod
    async def async_search(self, requests: List, top_k: int,reranker = None) -> list:
        """异步搜索方法"""
        pass