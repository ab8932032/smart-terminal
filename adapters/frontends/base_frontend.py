from abc import ABC, abstractmethod
from typing import Any
from core.event_bus import EventBus
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
        self.event_bus.subscribe("USER_INPUT", self._handle_user_input)
        self.event_bus.subscribe("CLEAR_HISTORY", self.clear_display)
        self.event_bus.subscribe("OUTPUT_UPDATE", self.handle_output_update)
        self.event_bus.subscribe("STATUS_UPDATE", self.handle_status_update)
        self.event_bus.subscribe("SECURITY_ALERT", self.handle_security_alert)
        self.event_bus.subscribe("ERROR", self.handle_error)

    @abstractmethod
    def start(self):
        """启动前端主循环"""
        pass

    # ---------- 事件处理接口 ----------
    @abstractmethod
    def handle_output_update(self, data: dict[str, Any]):
        """处理输出内容更新事件"""
        pass

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
    def clear_display(self,data: dict[str, Any]):
        """清空内容显示区域"""
        pass
    @abstractmethod
    def _handle_user_input(self, data: dict[str, Any]):
        """处理原始用户输入事件（预处理后转给具体处理器）"""
        pass
