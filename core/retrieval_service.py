# core/retrieval_service.py
from typing import List, Dict
from adapters.vectordb.base_vector_db import BaseVectorDBAdapter
from utils.config_loader import ConfigLoader
from utils.logger import get_logger
from core.ranker_factory import RankerFactory

logger = get_logger(__name__)


class RetrievalService:
    def __init__(self, vectordb_adapter: BaseVectorDBAdapter):
        """
        增强版检索服务，封装混合检索策略
        
        :param vectordb_adapter: 标准化vectordb适配器实例
        """
        self.vectordb = vectordb_adapter
        self.strategy = ConfigLoader.load_yaml("retrieval_strategy.yaml")

    async def hybrid_search(self, query: str, top_k: int = 5) -> List[Dict]:
        
        # 构建检索请求
        requests = self._build_search_requests(query, top_k)
        # 根据fusion定义的信息动态选择排序器
        fusion = self.strategy.get('fusion', {})
        reranker = RankerFactory.create_ranker(fusion.get('reranker', ""))
        # 执行检索
        raw_results = await self.vectordb.async_search(requests,top_k,reranker(fusion.get('weights', {}).get("percent",60)))
        return self._process_results(raw_results)
    
    def _process_results(self, raw_results: list) -> List[Dict]:
        """结果标准化处理"""
        processed = []
        seen = set()
        
        for group in raw_results:
            for hit in group:
                key = f"{hit.entity.filename}:{hash(hit.entity.text)}"
                if key not in seen:
                    processed.append({
                        "filename": hit.filename,
                        "text": hit.entity.text,
                        "score": hit.score
                    })
                    seen.add(key)
        
        return sorted(processed, key=lambda x: x["score"], reverse=True)
    
    def _build_search_requests(self, query: str, top_k: int) -> List[any]:
        """构建混合检索请求集合"""
        # 获取预处理后的查询向量
        return [
            # 稠密向量检索
            self.vectordb.create_dense_search_request(query, top_k),
            self.vectordb.create_sparse_search_request(query, top_k)
        ]

    def _format_results(self, raw_results: List) -> List[Dict]:
        """结果后处理流水线"""
        processed = []
        seen = set()
        
        for result_group in raw_results:
            for hit in result_group:
                # 基于内容指纹的去重
                content_hash = hash(f"{hit.entity.text}_{hit.entity.filename}")
                if content_hash not in seen:
                    processed.append({
                        "filename": hit.entity.filename,
                        "text": hit.entity.text,
                        "score": round(hit.score, 4),
                        "type": "dense" if hit.anns_field == "embedding" else "sparse"
                    })
                    seen.add(content_hash)
        
        # 按相关性分数排序
        return sorted(processed, key=lambda x: x["score"], reverse=True)[:self.strategy["fusion"]["limit"]]
