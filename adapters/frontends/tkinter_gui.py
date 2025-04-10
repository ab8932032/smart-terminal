import asyncio
import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Any, Dict
from adapters.frontends.base_frontend import BaseFrontend
from adapters.frontends.event_bindings import TkinterEventBinder
from core.event_bus import EventBus
from core.events import EventType
from services.session_manager import SessionManager

class TkinterFrontend(BaseFrontend):
    def __init__(self, event_bus: EventBus, session_manager: SessionManager, config: dict):
        self.event_bus = event_bus
        self.session_manager = session_manager
        self.config = config
        
        self.loop = asyncio.new_event_loop()  # 初始化事件循环

        # 重新创建 root 主窗口
        self.root = tk.Tk()
        self.root.title("Smart Terminal")
        self.root.geometry("800x600")  # 设置初始窗口大小
        super().__init__(event_bus, session_manager, config)
        self._response_buffer = ""  # 新增：用于缓存流式输出内容

    def _configure_theme(self):
        """配置Tkinter主题样式"""
        self.style = ttk.Style()

        # 更新颜色配置
        self.root.configure(bg='#f0f0f0')  # 调整背景颜色为更柔和的灰色
        self.style.configure('.', font=('微软雅黑', 11), padding=6)  # 调整字体大小和内边距

        # 组件样式
        self.style.configure('TButton',
                             padding=8,
                             background='#FF6600',  # 修改按钮背景颜色为橙色
                             foreground='white',  # 确保前景色明确设置
                             font=('微软雅黑', 10),  # 统一字体大小
                             relief='flat',
                             borderwidth=0,
                             focusthickness=0)
        self.color = {
            'primary': '#6200ea',
            'secondary': '#f8f9fa',
            'text': '#212529',
            'accent': '#0d6efd'
        }
        self.style.map('TButton',
                       foreground=[('active', 'white')],
                       background=self.color['primary'])
        
        self.style.configure('TLabel',
                             foreground='#212529',
                             background='#f8f9fa')
        
        self.style.configure('Status.TLabel',
                             font=('微软雅黑', 10),
                             foreground='#666666',
                             background='#f9f9f9')

        self.style.layout('Round.TButton',
                          [('Button.border',
                            {'children': [('Button.padding',
                                           {'children': [('Button.label', {'side': 'left', 'expand': 1})],
                                            'sticky': 'nsew'})],
                             'sticky': 'nsew'})])
        
        self.style.configure('Round.TButton',
                             bordercolor='transparent',
                             focuscolor='transparent')

       
    def _build_core_layout(self):
        # 主窗口布局配置
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.grid(row=0, column=0, sticky="nsew")
    
        # 子区域权重配置
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)   # 历史记录区域（占满剩余空间）
        main_frame.rowconfigure(1, weight=0, minsize=100)   # 输入区域（固定高度）
        main_frame.rowconfigure(2, weight=0, minsize=30)   # 状态栏（固定高度）
    
        # 各组件布局
        self._build_history_panel(main_frame)
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=1, column=0, sticky="ew", pady=(10,0))
        self._build_input_components(input_frame)
        self._build_status_bar(main_frame)
        main_frame.grid_rowconfigure(2, minsize=30)

    def _setup_event_system(self):
        """设置Tkinter事件系统"""
        TkinterEventBinder.bind_all(self.root, self.event_bus)

        # 自定义事件绑定
        self.root.bind("<Control-Return>", lambda e: self.event_bus.publish(EventType.USER_INPUT))

    def async_poll(self):
        self.loop.run_until_complete(asyncio.sleep(0))
        self.root.after(50, self.async_poll)
        
    def start(self):
        """启动前端主循环"""
        print("事件循环1。")
        self.async_poll()
        self.root.mainloop()
        self.loop.close()
            

    # ---------- 具体组件构建 ----------
    def _build_history_panel(self, parent):
        """构建聊天历史面板"""
        parent.rowconfigure(0, weight=1)
        self.chat_history = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            state='disabled',
            font=('微软雅黑', 12),
            padx=10,
            pady=10
        )
        self.chat_history.grid(row=0, column=0, sticky="nsew")
    
        # 新增样式配置移到此处（确保组件已创建）
        self.chat_history.tag_configure('user_input',
                                        foreground='#007BFF',
                                        font=('微软雅黑', 12, 'bold'))  # 加粗显示
        self.chat_history.tag_configure('response', foreground='#28A745')
        self.chat_history.tag_configure('think',
                                        foreground='#666666',
                                        font=('微软雅黑', 11, 'italic'))
        # 新增 assistant 样式
        self.chat_history.tag_configure('assistant', foreground='#0000FF')  # 蓝色字体

    def _build_input_components(self, parent):
        """构建输入组件"""
        self.input_area = tk.Text(parent,
                                  height=3,  # 减少输入框高度
                                  wrap=tk.WORD,
                                  font=('微软雅黑', 12),
                                  bg='#f8f9fa',  # 浅灰背景
                                  relief=tk.FLAT,
                                  highlightthickness=1,
                                  highlightcolor='#ced4da')
        self.input_area.grid(row=0, column=0, sticky="ew", padx=(0,15), pady=(0,10))
    
        parent.columnconfigure(0, weight=1)
    
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=0, column=1, sticky="ne")
        # 直接使用主样式 self.style，而非新建实例
        self.style.configure('Round.TButton',
                             foreground='black',  # 修改字体颜色为黑色
                             background=self.color['primary'],  # 深紫色背景
                             font=('微软雅黑', 10),
                             borderwidth=0,
                             relief="flat",
                             anchor="center")
        self.style.map('Round.TButton',
                       foreground=[('active', 'black')],  # 修改悬停时字体颜色为黑色
                       background=[('active', '#FF8C00')])  # 修改按钮悬停背景颜色为深橙色
        
        ttk.Button(btn_frame, text="发送", style='Round.TButton', command=self._on_send_button_click).pack(padx=5,pady=3, fill=tk.X)
        ttk.Button(btn_frame, text="清空", style='Round.TButton', command=self._on_clear_button_click).pack(padx=5,pady=3, fill=tk.X)

    def _build_status_bar(self, parent):
        """构建状态栏"""
        parent.rowconfigure(2, weight=0)
        self.status_label = ttk.Label(parent,
                                      text="就绪",
                                      style='Status.TLabel',
                                      anchor=tk.W,
                                      padding=(5,2),  # 内边距
                                      relief=tk.FLAT,
                                      borderwidth=1,
                                      foreground='#6c757d')
        self.status_label.grid(row=2, column=0, sticky="ew", pady=(10,0))

    # ---------- 事件处理接口实现 ----------

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
        return self.input_area.get("1.0", tk.END)  # 移除strip()保留换行符

    def clear_user_input(self):
        """清空用户输入区域"""
        self.input_area.delete("1.0", tk.END)

    def update_display(self, content: str, content_type: str = 'text'):
        self._append_history(content, content_type)

    def clear_display(self, data: dict[str, Any]):
        """清空内容显示区域"""
        self.chat_history.configure(state='normal')
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.configure(state='disabled')

    def handle_user_input(self,user_input:str):
        # 实现原始用户输入事件处理逻辑
        self.update_display(f"{user_input}\n", content_type='user_input')  # 使用现有的user_input样式

        # 显式验证会话ID
        session_id = self.session_manager.get_current_session()
        if not session_id:
            self.handle_error({
                "stage": "发送处理",
                "message": "未检测到有效会话"
            })
            return

        # 增加调试日志
        print(f"Publishing USER_INPUT: {user_input}")

        self.loop.create_task(self._async_publish_event({
            "text": user_input,
            "session_id": session_id
        }))

    # ---------- 私有方法 ----------
    def _append_history(self, content: str, tag: str = None):
        """安全更新聊天历史"""
        self.chat_history.configure(state='normal')
        
        # 根据不同的标签应用不同的样式
        if tag == 'user_input':
            self.chat_history.insert(tk.END, "用户: ", 'user_input')
            self.chat_history.insert(tk.END, f"{content}\n")
        elif tag == 'think':
            self.chat_history.insert(tk.END, content, 'think')
        elif tag == 'response':
            self.chat_history.insert(tk.END, content, 'response')
        else:
            self.chat_history.insert(tk.END, content,tag)
    
        self.chat_history.configure(state='disabled')
        self.chat_history.see(tk.END)

    def _on_send_button_click(self):
        """处理发送按钮点击事件"""
        user_input = self.input_area.get("1.0", "end-1c").strip()
        if not user_input:
            return
        self.handle_user_input(self.get_user_input());
    async def _async_publish_event(self, data):
        await self.event_bus.publish_async(EventType.USER_INPUT, data)
        self.clear_user_input()
    def _on_clear_button_click(self):
        """处理清空按钮点击事件"""
        session_id = self.session_manager.get_current_session()
        self.event_bus.publish(EventType.CLEAR_HISTORY, {
            "session_id": session_id
        })




