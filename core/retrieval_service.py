# core/retrieval_service.py
from typing import List, Dict
import logging
from pymilvus import AnnSearchRequest, RRFRanker
from utils.logger import get_logger

logger = get_logger(__name__)

class RetrievalService:
    def __init__(self, milvus_adapter):
        """
        增强版检索服务，封装混合检索策略
        
        :param milvus_adapter: 标准化Milvus适配器实例
        """
        self.milvus = milvus_adapter
        self._init_strategy_config()
        
    def _init_strategy_config(self):
        """初始化混合检索策略配置"""
        self.strategy = {
            # 稠密检索配置
            "dense": {
                "metric_type": "L2",
                "search_params": {"nprobe": 32}
            },
            # 稀疏检索配置
            "sparse": {
                "drop_ratio_search": 0.1
            },
            # 结果融合策略
            "fusion": {
                "ranker": RRFRanker(k=60),
                "limit": 5
            }
        }

    async def hybrid_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """执行完整检索流程"""
        # 向量化查询
        _, embeddings = self.milvus.chunk_text(query)
        
        # 构建检索请求
        requests = [
            AnnSearchRequest(
                data=embeddings,
                anns_field="embedding",
                param={"nprobe": self.strategy["dense"]["nprobe"]},
                limit=top_k
            ),
            AnnSearchRequest(
                data=[query],
                anns_field="sparse",
                param={"drop_ratio_search": self.strategy["sparse"]["drop_ratio"]},
                limit=top_k
            )
        ]
        
        # 执行检索
        raw_results = self.milvus.search(requests, top_k,self.strategy["fusion"]["ranker"])
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
                        "filename": hit.entity.filename,
                        "text": hit.entity.text,
                        "score": hit.score,
                        "type": "dense" if hit.anns_field == "embedding" else "sparse"
                    })
                    seen.add(key)
        
        return sorted(processed, key=lambda x: x["score"], reverse=True)
    
    def _build_search_requests(self, query: str, top_k: int) -> List[AnnSearchRequest]:
        """构建混合检索请求集合"""
        # 获取预处理后的查询向量
        _, embeddings = self.milvus.chunk_text(query)
        
        return [
            # 稠密向量检索
            AnnSearchRequest(
                data=embeddings,
                anns_field="embedding",
                param=self.strategy["dense"],
                limit=top_k
            ),
            # 稀疏向量检索
            AnnSearchRequest(
                data=[query],
                anns_field="sparse",
                param=self.strategy["sparse"],
                limit=top_k
            )
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

    def update_strategy(self, new_config: Dict):
        """
        动态更新检索策略
        
        :param new_config: 包含以下可选键的配置字典
            - nprobe: 稠密检索的搜索范围 (默认32)
            - drop_ratio: 稀疏检索的丢弃率 (默认0.1)
            - fusion_k: 融合策略的窗口大小 (默认60)
        """
        # 更新稠密检索参数
        if "nprobe" in new_config:
            self.strategy["dense"]["search_params"]["nprobe"] = new_config["nprobe"]
        
        # 更新稀疏检索参数
        if "drop_ratio" in new_config:
            self.strategy["sparse"]["drop_ratio_search"] = new_config["drop_ratio"]
        
        # 更新融合策略
        if "fusion_k" in new_config:
            self.strategy["fusion"]["ranker"] = RRFRanker(k=new_config["fusion_k"])
        
        logger.info(f"检索策略更新: {new_config}")