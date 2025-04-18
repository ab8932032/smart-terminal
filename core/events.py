# core/events.py
from enum import Enum

class EventType(str, Enum):
    # 用户交互事件
    USER_INPUT = "user_input"             # 数据格式: str
    CLEAR_HISTORY = "clear_history"       # 数据格式: None

    # 系统状态事件
    STATUS_UPDATE = "status_update"       # 数据格式: {"state": "processing"/"idle"}
    SECURITY_ALERT = "security_alert"     # 数据格式: {"type": alert_type, "details": ...}

    # 知识检索事件
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"   # 数据格式: str (query)
    KNOWLEDGE_RESULT = "knowledge_result"       # 数据格式: List[dict]
    KNOWLEDGE_FILTERED = "knowledge_filtered"   # 数据格式: List[dict]
    KNOWLEDGE_READY = "knowledge_ready"  # 到知识检索事件部

    # 问答生成事件
    GENERATION_START = "generation_start"       # 数据格式: {"question": str}
    GENERATION_COMPLETE = "generation_complete" # 数据格式: {"answer": str, "sources": list}

    # 命令执行事件
    COMMAND_START = "command_start"       # 数据格式: str (command)
    COMMAND_RESULT = "command_result"     # 数据格式: {"status": "success"/"error", ...}
    COMMAND_SUCCESS = "command_success"
    COMMAND_ERROR = "command_error"

    ERROR = "error"                       # 数据格式: {"stage": str, "error": str}

    # 历史管理事件
    HISTORY_CLEARED = "history_cleared"   # 数据格式: None

    # 输出事件
    STREAM_START = "stream_start"           # 流式开始
    RESPONSE_CHUNK = "response_chunk"       # 流式响应片段
    STREAM_END = "stream_end"               # 流式结束

    CANCEL_OPERATION = "cancel_operation"

    CONTEXT_MENU = "context_menu"

