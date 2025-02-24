import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from utils.logger import get_logger
from utils.config_loader import ModelConfig

class SessionManager:
    def __init__(self, config: ModelConfig = None):
        """
        对话会话管理服务
        :param config: 配置加载器实例
        """
        self.logger = get_logger(__name__)
        self.config = config or ModelConfig.load()
        self._lock = threading.Lock()

        # 初始化存储路径
        self.storage_path = Path(self.config.get('session.storage_path', './sessions'))
        self._init_storage()

        # 内存会话存储
        self.active_sessions = {}  # {session_id: SessionData}

    def _init_storage(self):
        """初始化会话存储目录"""
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Session storage initialized at: {self.storage_path}")
        except Exception as e:
            self.logger.error(f"Failed to initialize session storage: {str(e)}")
            raise

    def create_session(self, user_id: str = "default") -> str:
        """
        创建新会话
        :param user_id: 用户标识符
        :return: 新会话ID
        """
        session_id = f"{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        with self._lock:
            self.active_sessions[session_id] = {
                "history": [],
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "last_accessed": datetime.now().isoformat(),
                    "user_id": user_id
                }
            }
        return session_id

    def add_message(self, session_id: str, role: str, content: str, metadata: dict = None):
        """
        添加消息到指定会话
        :param session_id: 会话ID
        :param role: 角色（user/assistant）
        :param content: 消息内容
        """
        with self._lock:
            if session_id not in self.active_sessions:
                raise ValueError(f"Session {session_id} not found")

            # 更新会话最后访问时间
            self.active_sessions[session_id]["metadata"]["last_accessed"] = datetime.now().isoformat()
            self.active_sessions[session_id]["history"].append({
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat()
            })
            self._auto_save(session_id)

    def get_history(self, session_id: str, max_length: int = 10) -> List[Dict]:
        """
        获取会话历史（最近N条）
        :param session_id: 会话ID
        :param max_length: 最大返回条数
        :return: 历史消息列表
        """
        with self._lock:
            if session_id not in self.active_sessions:
                return []

            history = self.active_sessions[session_id]["history"]
            return history[-max_length:]

    def clear_history(self, session_id: str):
        """
        清空指定会话历史
        :param session_id: 会话ID
        """
        with self._lock:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["history"] = []
                self._delete_session_file(session_id)

    def _auto_save(self, session_id: str):
        """自动保存会话到文件（当历史记录超过阈值时）"""
        if len(self.active_sessions[session_id]["history"]) % 5 == 0:
            self.save_session(session_id)

    def save_session(self, session_id: str):
        """持久化会话到文件"""
        try:
            session_data = self.active_sessions.get(session_id)
            if not session_data:
                return

            file_path = self.storage_path / f"{session_id}.json"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f"Failed to save session {session_id}: {str(e)}")

    def load_session(self, session_id: str) -> bool:
        """从文件加载会话"""
        try:
            file_path = self.storage_path / f"{session_id}.json"
            if not file_path.exists():
                return False

            with open(file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            with self._lock:
                self.active_sessions[session_id] = session_data
            return True

        except Exception as e:
            self.logger.error(f"Failed to load session {session_id}: {str(e)}")
            return False

    def _delete_session_file(self, session_id: str):
        """删除会话文件"""
        try:
            file_path = self.storage_path / f"{session_id}.json"
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            self.logger.error(f"Failed to delete session file {session_id}: {str(e)}")
    def append_chunk(self, session_id: str, chunk: Dict):  # 修改参数类型
        """追加流式响应片段"""
        with self._lock:
            if session_id not in self.active_sessions:
                return
    
            if "response_buffer" not in self.active_sessions[session_id]:
                self.active_sessions[session_id]["response_buffer"] = []
    
            self.active_sessions[session_id]["response_buffer"].append(chunk)
    
    def get_response_buffer(self, session_id: str) -> list:
        """获取当前响应缓冲区"""
        return self.active_sessions.get(session_id, {}).get("response_buffer", [])
    
    def clear_response_buffer(self, session_id: str):
        """清空响应缓冲区"""
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["response_buffer"] = []