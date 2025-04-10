from abc import ABC, abstractmethod
from typing import Any
from core.event_bus import EventBus
from core.events import EventType
from services.session_manager import SessionManager
from utils.config_loader import ModelConfig

class BaseFrontend(ABC):
    """前端系统抽象基类，定义所有前端实现必须遵守的接口"""

    def __init__(self,
                 event_bus: EventBus,
                 session_manager: SessionManager,
                 config: dict[str, Any]):
        """
        初始化前端基础组件
        :param event_bus: 事件总线实例
        :param session_manager: 会话管理器实例 
        :param config: 应用配置
        """
        self.event_bus = event_bus
        self.session_manager = session_manager
        self.config = config
        self._bootstrap_ui()
        self.in_think = False  # 新增：用于标记是否在 <think> 标签内

    def _bootstrap_ui(self):
        """引导式UI初始化（模板方法模式）"""
        self._configure_theme()
        self._build_core_layout()
        self._setup_event_system()
        self._subscribe_core_events()

    @abstractmethod
    def _configure_theme(self):
        """配置视觉主题（字体/颜色/样式）"""
        pass

    @abstractmethod
    def _build_core_layout(self):
        """构建核心界面布局"""
        pass

    @abstractmethod
    def _setup_event_system(self):
        """设置事件响应系统（绑定+处理器注册）"""
        pass

    def _subscribe_core_events(self):
        """订阅核心事件总线消息（可被子类扩展）"""
        self.event_bus.subscribe(EventType.CLEAR_HISTORY, self.clear_display)

        self.event_bus.subscribe(EventType.STREAM_START, self.handle_stream_start)
        self.event_bus.subscribe(EventType.RESPONSE_CHUNK, self.handle_response_chunk)
        self.event_bus.subscribe(EventType.STREAM_END, self.handle_stream_end)
        self.event_bus.subscribe(EventType.STATUS_UPDATE, self.handle_status_update)
        self.event_bus.subscribe(EventType.SECURITY_ALERT, self.handle_security_alert)
        self.event_bus.subscribe(EventType.ERROR, self.handle_error)

    @abstractmethod
    def start(self):
        """启动前端主循环"""
        pass

    # ---------- 事件处理接口 ----------
    
    def handle_stream_start(self, data: dict[str, Any]):
        """处理输出内容更新事件"""
        content_type = data.get("type", "text")
        self.update_display("AI: \n\n", content_type='assistant')
    
    def handle_stream_end(self, data: dict[str, Any]):
        """处理输出内容更新事件"""
        self.update_display("\n", content_type='assistant')

    @abstractmethod
    def handle_status_update(self, data: dict[str, Any]):
        """处理系统状态更新事件"""
        pass

    @abstractmethod
    def handle_error(self, data: dict[str, Any]):
        """处理错误事件"""
        pass

    @abstractmethod
    def handle_security_alert(self, data: dict[str, Any]):
        """处理安全警报事件（权限校验/敏感操作拦截）"""
        pass

    def handle_response_chunk(self, event_data: dict[str, Any]):
        """处理流式响应分块（支持 <think> 和 </think> 标签包裹的思考内容）"""
        chunk = event_data["chunk"]
        content = chunk["content"]

        # 处理内容中的 <think> 和 </think> 标签
        if "<think>" in content:
            before_think, rest = content.split("<think>", 1)
            if before_think:
                self.update_display(before_think, content_type='response')
            self.update_display("思考中...\n", content_type='think')  # 替换 <think> 标签
            content = rest
            self.in_think = True

        if "</think>" in content and self.in_think:
            think_content, after_think = content.split("</think>", 1)
            self.update_display(think_content, content_type='think')
            self.update_display("思考完成.\n", content_type='think')  # 替换 </think> 标签
            content = after_think
            self.in_think = False

        # 如果在 <think> 标签内，继续使用 think 标记
        if self.in_think:
            self.update_display(content, content_type='think')
        else:
            if content:
                self.update_display(content, content_type='response')

    # ---------- 用户交互接口 ----------
    @abstractmethod
    def get_user_input(self) -> str:
        """获取用户输入内容"""
        pass

    @abstractmethod
    def clear_user_input(self):
        """清空用户输入区域"""
        pass

    @abstractmethod
    def update_display(self, content: str, content_type: str = "text"):
        """更新内容显示区域"""
        pass

    @abstractmethod
    def clear_display(self, data: dict[str, Any]):
        """清空内容显示区域"""
        pass

    @abstractmethod
    def handle_user_input(self,user_input:str):
        """处理原始用户输入事件（预处理后转给具体处理器）"""
        pass