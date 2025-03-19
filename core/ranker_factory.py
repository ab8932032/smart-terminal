from typing import Callable, Dict


class RankerFactory:
    @staticmethod
    def create_ranker(ranker_type: str) -> Callable:
        
        if ranker_type == 'RRFRanker':
            from pymilvus import RRFRanker
            return lambda limit: RRFRanker(limit)
        # 可以在这里扩展其他类型的ranker
        raise ValueError(f"Unsupported ranker type: {ranker_type}")
        