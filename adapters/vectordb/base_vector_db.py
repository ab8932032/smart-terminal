from typing import Dict

class BaseVectorDBAdapter:
    def _build_metadata(self, data: Dict) -> Dict:
        # 构建元数据，例如：
        # metadata = {
        #     "source": "user_input",
        #     "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #     "user_id": "default",
        #     "session_id": "default",
        #     "question": data.get("question", ""),
        #     "answer": data.get("answer", ""),
        }