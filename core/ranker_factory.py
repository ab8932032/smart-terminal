from typing import Callable, Dict


class RankerFactory:
    @staticmethod
    def create_ranker(ranker_config: Dict) -> Callable:
        ranker_type = ranker_config.get('type')
        
        if ranker_type == 'RRFRanker':
            from pymilvus import RRFRanker
            return lambda limit: RRFRanker(limit)
        # 可以在这里扩展其他类型的ranker
        raise ValueError(f"Unsupported ranker type: {ranker_type}")
        