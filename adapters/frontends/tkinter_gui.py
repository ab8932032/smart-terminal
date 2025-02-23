# adapters/frontends/tkinter_gui.py
import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Optional
from core.event_bus import EventBus
from services.session_manager import SessionManager
from adapters.frontends.event_bindings import TkinterEventBinder

class TkinterFrontend:
    def __init__(
            self,
            master: tk.Tk,
            event_bus: EventBus,
            session_manager: SessionManager
    ):
        """
        Tkinter前端界面适配器
        :param master: 根窗口对象
        :param event_bus: 事件总线实例
        :param session_manager: 会话管理实例
        """
        self.master = master
        self.event_bus = event_bus
        self.session_manager = session_manager

        # 纯界面初始化
        self._configure_base_styles()
        self._build_interface()
        self._setup_event_bindings()

    # region 界面构建
    def _configure_base_styles(self):
        """配置基础样式"""
        self.style = ttk.Style()
        self.style.configure('TButton', font=('微软雅黑', 10), padding=6)
        self.style.configure('Status.TLabel', font=('微软雅黑', 10), foreground='gray')
        self.master.option_add('*background', '#f0f0f0')
        self.master.option_add('*foreground', '#333333')

    def _build_interface(self):
        """构建完整界面布局"""
        main_frame = ttk.Frame(self.master)
        main_frame.pack(expand=True, fill='both', padx=10, pady=10)

        # 聊天历史区域
        self.chat_history = scrolledtext.ScrolledText(
            main_frame,
            wrap=tk.WORD,
            state='disabled',
            font=('微软雅黑', 12),
            padx=15,
            pady=15
        )
        self.chat_history.pack(expand=True, fill='both')

        # 输入面板
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill='x', pady=(10, 0))
        self._build_input_components(input_frame)

        # 状态栏
        self.status_label = ttk.Label(
            main_frame,
            text="就绪",
            style='Status.TLabel'
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_input_components(self, parent: ttk.Frame):
        """构建输入区域组件"""
        self.input_area = tk.Text(
            parent,
            height=4,
            font=('微软雅黑', 12)
        )
        self.input_area.pack(side=tk.LEFT, expand=True, fill=tk.X)

        action_frame = ttk.Frame(parent)
        action_frame.pack(side=tk.RIGHT, padx=(10, 0))

        ttk.Button(
            action_frame,
            text="发送",
            command=lambda: self.event_bus.publish("USER_INPUT")
        ).pack(side=tk.TOP, pady=2)

        ttk.Button(
            action_frame,
            text="清空",
            command=lambda: self.event_bus.publish("CLEAR_HISTORY")
        ).pack(side=tk.TOP)
    # endregion

    # region 事件处理
    def _setup_event_bindings(self):
        """设置事件绑定"""
        TkinterEventBinder.bind_all(self.master, self.event_bus)
        self.event_bus.subscribe("OUTPUT_UPDATE", self.handle_output_update)
        self.event_bus.subscribe("STATUS_UPDATE", self.handle_status_update)
        self.event_bus.subscribe("ERROR", self.handle_error)

    def handle_output_update(self, data: dict):
        """处理输出更新事件"""
        self.chat_history.configure(state='normal')
        self.chat_history.insert(tk.END, data.get("content", "") + "\n\n")
        self.chat_history.configure(state='disabled')
        self.chat_history.see(tk.END)

    def handle_status_update(self, data: dict):
        """处理状态更新事件"""
        status_map = {
            "processing": "处理中...",
            "idle": "就绪",
            "generating": "生成回答中"
        }
        self.status_label.config(text=status_map.get(data.get("state"), "未知状态"))

    def handle_error(self, data: dict):
        """处理错误事件"""
        error_msg = f"[错误] {data.get('stage', '未知阶段')}: {data.get('message', '未知错误')}"
        self.chat_history.configure(state='normal')
        self.chat_history.insert(tk.END, error_msg + "\n", "error")
        self.chat_history.configure(state='disabled')
    # endregion

    # region 纯界面操作
    def clear_display(self):
        """清空显示区域"""
        self.chat_history.configure(state='normal')
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.configure(state='disabled')

    def get_input_text(self) -> str:
        """获取输入框内容"""
        return self.input_area.get("1.0", "end-1c").strip()

    def clear_input(self):
        """清空输入框"""
        self.input_area.delete("1.0", tk.END)
    # endregion
