import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Any, Dict
from adapters.frontends.base_frontend import BaseFrontend
from adapters.frontends.event_bindings import TkinterEventBinder
from core.event_bus import EventBus
from services.session_manager import SessionManager

class TkinterFrontend(BaseFrontend):
    def __init__(self, event_bus: EventBus, session_manager: SessionManager, config: Dict[str, Any]):
        super().__init__(event_bus, session_manager, config)
        self.root = tk.Tk()
        self.root.title("Smart Terminal GUI")
        self._build_core_layout()

    def _configure_theme(self):
        """配置Tkinter主题样式"""
        self.style = ttk.Style()

        # 基础颜色配置
        self.root.configure(bg='#f0f0f0')
        self.style.configure('.', font=('微软雅黑', 10))

        # 组件样式
        self.style.configure('TButton',
                             padding=6,
                             background='#e1e1e1',
                             foreground='#333333')

        self.style.configure('Status.TLabel',
                             font=('微软雅黑', 10),
                             foreground='#666666',
                             background='#f0f0f0')

    def _build_core_layout(self):
        """构建核心界面布局"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 历史记录区域
        self._build_history_panel(main_frame)

        # 输入区域
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(10, 0))
        self._build_input_components(input_frame)

        # 状态栏
        self._build_status_bar(main_frame)
        
    def _setup_event_system(self):
        """设置Tkinter事件系统"""
        TkinterEventBinder.bind_all(self.root, self.event_bus)

        # 自定义事件绑定
        self.root.bind("<Control-Return>", lambda e: self.event_bus.publish("USER_INPUT"))

    def start(self):
        """启动前端主循环"""
        self.root.mainloop()

    # ---------- 具体组件构建 ----------
    def _build_history_panel(self, parent):
        """构建聊天历史面板"""
        self.chat_history = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            state='disabled',
            font=('微软雅黑', 12),
            padx=15,
            pady=15,
            bg='#ffffff'
        )
        self.chat_history.pack(fill=tk.BOTH, expand=True)

    def _build_input_components(self, parent):
        """构建输入组件"""
        # 输入文本框
        self.input_area = tk.Text(
            parent,
            height=4,
            font=('微软雅黑', 12),
            bg='#ffffff'
        )
        self.input_area.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        # 操作按钮区域
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(side=tk.RIGHT)

        # 发送按钮
        ttk.Button(
            btn_frame,
            text="发送",
            command=self._on_send_button_click
        ).pack(pady=2)

        # 清空按钮
        ttk.Button(
            btn_frame,
            text="清空",
            command=self._on_clear_button_click
        ).pack()

    def _build_status_bar(self, parent):
        """构建状态栏"""
        self.status_label = ttk.Label(
            parent,
            text="就绪",
            style='Status.TLabel'
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    # ---------- 事件处理接口实现 ----------
    def handle_output_update(self, data: Dict[str, Any]):
        content = data.get("content", "")
        self._append_history(content)

    def handle_status_update(self, data: Dict[str, Any]):
        status_map = {
            "processing": "🔄 处理中...",
            "idle": "✅ 就绪",
            "generating": "🤖 生成中"
        }
        self.status_label.config(text=status_map.get(data.get("state"), "❓ 未知状态"))

    def handle_error(self, data: Dict[str, Any]):
        error_msg = f"⛔ 错误 [{data.get('stage', '未知阶段')}]: {data.get('message', '未知错误')}"
        self._append_history(error_msg, tag="error")

    def handle_security_alert(self, data: Dict[str, Any]):
        # 实现安全警报事件处理逻辑
        alert_msg = f"🚨 安全警报 [{data.get('type', '未知类型')}]: {data.get('message', '未知警报')}"
        self._append_history(alert_msg, tag="alert")

    # ---------- 用户交互接口实现 ----------
    def get_user_input(self) -> str:
        return self.input_area.get("1.0", "end-1c").strip()

    def clear_user_input(self):
        """清空用户输入区域"""
        self.input_area.delete("1.0", tk.END)

    def update_display(self, content: str, content_type: str = "text"):
        self._append_history(content)

    def clear_display(self, data: dict[str, Any]):
        """清空内容显示区域"""
        self.chat_history.configure(state='normal')
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.configure(state='disabled')

    def _handle_user_input(self, data: Dict[str, Any]):
        # 实现原始用户输入事件处理逻辑
        user_input = self.get_user_input()
        self.clear_user_input()
        self.event_bus.publish("USER_INPUT", {"content": user_input})

    # ---------- 私有方法 ----------
    def _append_history(self, content: str, tag: str = None):
        """安全更新聊天历史"""
        self.chat_history.configure(state='normal')
        self.chat_history.insert(tk.END, content + "\n\n", tag)
        self.chat_history.configure(state='disabled')
        self.chat_history.see(tk.END)

    def _on_send_button_click(self):
        """处理发送按钮点击事件"""
        user_input = self.input_area.get("1.0", tk.END).strip()
        if not user_input:
            return

        session_id = self.session_manager.get_current_session()
        self.event_bus.publish("USER_INPUT", {
            "text": user_input,
            "session_id": session_id
        })
        self.clear_user_input()  # 清空输入框

    def _on_clear_button_click(self):
        """处理清空按钮点击事件"""
        session_id = self.session_manager.get_current_session()
        self.event_bus.publish("CLEAR_HISTORY", {
            "session_id": session_id
        })

