import os
import tkinter as tk
from tkinter import scrolledtext, ttk, simpledialog
import requests
import json
import threading
import subprocess
import datetime
from services.command_processor import CommandProcessor  # 修正导入路径
from adapters.vectordb.milvus_adapter import MilvusAdapter
from utils.config_loader import ModelConfig  # 新增配置引用
from utils.logger import get_logger
from utils.template_manager import TemplateManager
from core.qa_engine import QAEngine

#API_URL = "http://localhost:11434/api/chat"
#MODEL_NAME = "deepseek-r1:7b"
#MODEL_NAME= "qwen2.5"

logger = get_logger(__name__)

class TkinterFrontend:
    def __init__(self, master):
        self.master = master
        self.config = ModelConfig.load()  # 使用统一配置
        self._init_components()
        self._setup_infrastructure()
        self._bind_events()
        
        # 应改为从配置读取
        self.api_url = self.config.get('model_providers.ollama.endpoint') + "/api/chat"
        self.model_name = self.config.get('model_providers.ollama.models.default')

    def _init_components(self):
        """初始化界面组件"""
        self.master.title("DeepSeek 智能终端")
        self.master.geometry("1280x960")
        
        # 样式配置
        self.style = ttk.Style()
        self._configure_styles()
        
        # 主界面布局
        self._build_main_frame()
        self._build_chat_history()
        self._build_input_panel()
        self._build_status_bar()

    def _configure_styles(self):
        """配置界面样式"""
        self.style.configure('TButton', font=('微软雅黑', 10), padding=6)
        self.style.configure('TFrame', background='#f0f0f0')
        self.style.configure('Status.TLabel', font=('微软雅黑', 10), foreground='gray')

    def _build_main_frame(self):
        """构建主容器"""
        self.main_frame = ttk.Frame(self.master)
        self.main_frame.pack(expand=True, fill='both', padx=10, pady=10)

    def _build_chat_history(self):
        """构建聊天历史区域"""
        self.chat_history = scrolledtext.ScrolledText(
            self.main_frame, 
            wrap=tk.WORD,
            state='disabled',
            font=('微软雅黑', 12),
            padx=15,
            pady=15
        )
        self.chat_history.pack(expand=True, fill='both')

    def _build_input_panel(self):
        """构建输入面板"""
        input_frame = ttk.Frame(self.main_frame)
        input_frame.pack(fill='x', pady=(10, 0))
        
        # 输入区域
        self.input_area = scrolledtext.ScrolledText(
            input_frame,
            wrap=tk.WORD,
            height=4,
            font=('微软雅黑', 12)
        )
        self.input_area.pack(side='left', expand=True, fill='both')
        
        # 按钮面板
        self._build_button_panel(input_frame)

    def _build_button_panel(self, parent):
        """构建右侧按钮面板"""
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(side='right', padx=(10, 0))
        
        buttons = [
            ("发送", self.send_message, "Ctrl+Return"),
            ("清空", self.clear_input, "Escape"),
            ("清空历史", self.clear_history, None)
        ]
        
        for text, command, shortcut in buttons:
            btn = ttk.Button(btn_frame, text=text, command=command)
            btn.pack(pady=5, fill='x')

    def _build_status_bar(self):
        """构建状态栏"""
        self.status_bar = ttk.Label(
            self.main_frame,
            text="就绪",
            style='Status.TLabel'
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _setup_infrastructure(self):
        """初始化基础设施"""
        self.milvus = MilvusAdapter()
        self.qa_engine = QAEngine()  # 通过问答引擎访问
        self.conversation_history = []
        self._init_file_path()
        self._load_system_prompt()
        
    def _load_system_prompt(self):
        """加载系统提示词"""
        system_prompt = TemplateManager.render('system_prompt.jinja')
        self._append_message('system', system_prompt)
    def __init__(self, master):
        self.master = master
        self.milvus = MilvusAdapter()
        master.title("DeepSeek 智能终端")
        master.geometry("1280x960")
        
        # 样式配置
        self.style = ttk.Style()
        self._configure_styles()
        
        # 界面布局
        self._create_widgets()
        self.is_responding = False
        # 添加对话历史记录
        self.conversation_history = []
        
        """
        subprocess.run(
                ['powershell', '-Command', 'ollama serve'],
                check=True,
                shell=True
        )
        """
        subprocess.run(
                ['powershell', '-Command', f'ollama pull {self.model_name}'],
                check=True,
                shell=True
        )
        # 初始化文件路径
        self._init_file_path()
        
        self._update_display(f"我是一个智能终端，请开始你的提问...\n\n\n", 'system')

    def _save_to_file(self, text):
        """将问答结果保存到本地文件"""
        with open(self.file_path, 'a', encoding='utf-8') as file:
            file.write(text)

    def _get_ai_response(self, prompt):
        """获取AI响应（适配多轮对话API）"""
        messages = self.conversation_history.copy()
        res = self.milvus.search_in_milvus(prompt, 5)
        #res = [item for item in res if item['score'] > 0.7]  # 增加分数过滤
        if not res:
            res_str = "[]"
        else:
            res_str = json.dumps({
                "valid_results": [{
                    "filename": item['entity']['filename'],
                    "text": item['entity']['text'],
                    "score": round(item['score'], 2)
                } for item in res]
            }, ensure_ascii=False)
            #res_str = json.dumps(res, ensure_ascii=False)
        messages.append({
            "role": "user",
            "content": f"""
                【问题处理指令】
                请严格按照以下步骤处理：
                
                [步骤1]
                milvus知识库原始数据（JSON）：
                {res_str}
                
                [步骤2] 相关性分析
                用户问题：{prompt}"""
        })
        data = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "options": { 
                "temperature": 0.1
            }
        }

        try:
            response = requests.post(self.api_url, json=data, stream=True)
            response.raise_for_status()
            full_response = []
            self._update_display(f"智能终端：\n", 'system')
            for line in response.iter_lines():
                if line:
                    try:
                        json_data = json.loads(line.decode('utf-8'))
                        if 'message' in json_data:
                            # 解析 message 字段中的 JSON 数据
                            message_content = json_data["message"].get("content", "")
                            self._stream_char(message_content)
                            full_response.append(message_content)
                    except json.JSONDecodeError:
                        self._show_error("接收到无效响应格式")

            self._stream_char("\n=========================================================================================================================\n")
            final_response = ''.join(full_response)
            self._process_commands(final_response)
            self.conversation_history.append({"role": "user", "content": prompt})
            self.conversation_history.append({"role": "assistant", "content": final_response})
            self._save_to_file("user:\n" + json.dumps(messages,ensure_ascii = False) + "\n")
            self._save_to_file("assistant:\n" + final_response + "\n=========================================================================================================================\n")
            self._update_status("就绪")

        except requests.RequestException as e:
            self._show_error(f"API请求失败: {str(e)}")
        finally:
            self.is_responding = False

    def _update_display(self, text, tag='assistant', end=True):
        """更新聊天显示"""
        self.chat_history.configure(state='normal')
        self.chat_history.insert(tk.END, text, tag)
        self.chat_history.see(tk.END)
        self.chat_history.configure(state='disabled')

    def _configure_styles(self):
        """配置界面样式"""
        self.style.configure('TButton', font=('微软雅黑', 10), padding=6)
        self.style.configure('TFrame', background='#f0f0f0')
        self.style.configure('Status.TLabel', font=('微软雅黑', 10), foreground='gray')
        self.master.option_add('*TScrolledText*Font', ('微软雅黑', 12))
        self.master.option_add('*background', '#f0f0f0')
        self.master.option_add('*foreground', '#333333')

    def _create_widgets(self):
        """创建界面组件"""
        main_frame = ttk.Frame(self.master)
        main_frame.pack(expand=True, fill='both', padx=10, pady=10)
        
        self.chat_history = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, state='disabled', padx=15, pady=15, height=20)
        self.chat_history.pack(expand=True, fill='both', pady=(0, 10))
        
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill='x')
        
        self.input_area = scrolledtext.ScrolledText(input_frame, wrap=tk.WORD, height=4, font=('微软雅黑', 12), padx=10, pady=10)
        self.input_area.pack(side='left', expand=True, fill='both')
        
        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(side='right', fill='y', padx=(10, 0))
        
        style = ttk.Style()
        style.configure('Center.TButton', anchor='center')
        self.send_btn = ttk.Button(btn_frame, text="      发送\n(Ctrl+Enter)", command=self.send_message, width=12, style='Center.TButton')
        self.send_btn.pack(pady=5)
        
        self.clear_btn = ttk.Button(btn_frame, text="清空", command=self.clear_input, width=12)
        self.clear_btn.pack(pady=5)
        
        # 添加清空历史记录按钮
        self.clear_history_btn = ttk.Button(btn_frame, text="清空历史", command=self._clear_history, width=12)
        self.clear_history_btn.pack(pady=5)
        
        self.status_bar = ttk.Label(main_frame, text="就绪", style='Status.TLabel')
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.input_area.bind("<Control-Return>", lambda e: self.send_message())
        self.input_area.bind("<Escape>", lambda e: self.clear_input())
        bold_font = ('微软雅黑', 12, 'bold')
        self.chat_history.tag_config('user',font=('微软雅黑', 12), foreground='#1E88E5')
        self.chat_history.tag_config('assistant',font=('微软雅黑', 12), foreground='#43A047')
        self.chat_history.tag_config('system',font=bold_font, foreground='#6D4C41')
        self.chat_history.tag_config('error', foreground='#D32F2F')
        self.chat_history.tag_config('divider', foreground='#BDBDBD')

    def clear_input(self):
        """清空输入框"""
        self.input_area.delete("1.0", tk.END)
        self.input_area.focus_set()
    def _clear_history(self):
        """清空历史记录但保留system的JSON"""
        # 保留初始的system消息
        initial_system_message = self.conversation_history[0]
        self.conversation_history = [initial_system_message]
        
        # 清空聊天显示
        self.chat_history.configure(state='normal')
        self.chat_history.delete("1.0", tk.END)
        self.chat_history.insert(tk.END, f"我是一个智能终端，请开始你的提问...\n\n\n", 'system')
        self.chat_history.configure(state='disabled')
        
        # 清空文件内容并保留初始system消息
        with open(self.file_path, 'w', encoding='utf-8') as file:
            file.write("user:\n\nassistant:\n我是一个智能终端，请开始你的提问...\n\n\n=========================================================================================================================\n")

    def _bind_events(self):
        """绑定事件处理"""
        self.input_area.bind("<Control-Return>", lambda e: self.send_message())
        self.input_area.bind("<Escape>", lambda e: self.clear_input())
        
        # 配置文本标签样式
        self._configure_text_tags()

    def _configure_text_tags(self):
        """配置聊天文本样式"""
        bold_font = ('微软雅黑', 12, 'bold')
        self.chat_history.tag_config('user', font=('微软雅黑', 12), foreground='#1E88E5')
        self.chat_history.tag_config('assistant', font=('微软雅黑', 12), foreground='#43A047')
        self.chat_history.tag_config('system', font=bold_font, foreground='#6D4C41')
        self.chat_history.tag_config('error', foreground='#D32F2F')
        self.chat_history.tag_config('divider', foreground='#BDBDBD')

    def _append_message(self, role: str, content: str):
        """添加消息到对话历史"""
        self.conversation_history.append({"role": role, "content": content})
        
    def _init_file_path(self):
        """初始化日志文件路径"""
        log_dir = self.config.get("logging.path", "logs")
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file_path = os.path.join(log_dir, f"chat_history_{timestamp}.txt")

    # region 核心功能方法
    def send_message(self):
        """处理用户消息发送"""
        if self.is_responding:
            return
            
        if user_text := self.input_area.get("1.0", tk.END).strip():
            self.clear_input()
            self._display_user_message(user_text)
            self._start_response_thread(user_text)

    def _display_user_message(self, text: str):
        """显示用户消息"""
        self._update_display(f"用户：\n", 'system')
        self._update_display(f"{text}\n\n", 'user')
        
    def _start_response_thread(self, prompt: str):
        """启动响应线程"""
        self.is_responding = True
        threading.Thread(
            target=self._get_ai_response,
            args=(prompt,),
            daemon=True
        ).start()

    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = [self.conversation_history[0]]  # 保留系统提示
        self._update_display("历史记录已重置\n", 'system')
        self._reset_chat_display()

    def _reset_chat_display(self):
        """重置聊天显示区域"""
        self.chat_history.configure(state='normal')
        self.chat_history.delete("1.0", tk.END)
        self.chat_history.insert(tk.END, "对话历史已清空\n", 'system')
        self.chat_history.configure(state='disabled')
    # endregion

    # region 工具方法
    def _stream_char(self, char: str):
        """流式输出字符"""
        self.master.after(0, self._update_display, char, 'assistant', False)
    
    def _update_status(self, message: str):
        """更新状态栏"""
        self.status_bar.config(text=message)

    def _show_error(self, message: str):
        """显示错误信息"""
        logger.error(message)
        self._update_display(f"\n⚠️ {message}\n", 'error')
    # endregion

    def _process_commands(self, response: str):
        """处理响应中的系统命令"""
        if commands := CommandProcessor.detect_commands(response):
            self.master.after(
                0, 
                self._confirm_command_execution, 
                commands, 
                response
            )

    def _confirm_command_execution(self, commands: list, context: str):
        """确认命令执行对话框"""
        cmd_list = "\n".join([f"{i+1}. {cmd}" for i, cmd in enumerate(commands)])
        choice = simpledialog.askinteger(
            "命令检测",
            f"发现 {len(commands)} 个潜在命令\n\n上下文摘要：{context[:150]}...\n\n{cmd_list}\n\n输入要执行的命令编号（0取消）：",
            parent=self.master,
            minvalue=0,
            maxvalue=len(commands)
        )
        
        if choice and 0 < choice <= len(commands):
            self._execute_safe_command(commands[choice-1])

    def _execute_safe_command(self, command: str):
        """执行安全检查后的命令"""
        if CommandProcessor.is_dangerous_command(command):
            self._show_error("检测到危险命令，已阻止执行")
        else:
            self._execute_command(command)

    def _execute_command(self, command: str):
        """执行系统命令"""
        def execution_thread():
            try:
                self._update_status(f"正在执行: {command[:30]}...")
                result = CommandProcessor.execute_command(command)
                self._display_command_result(command, result)
            except Exception as e:
                logger.exception("命令执行失败")
                self._show_error(f"命令执行失败: {str(e)}")
            finally:
                self._update_status("就绪")
        
        threading.Thread(target=execution_thread, daemon=True).start()

    def _display_command_result(self, command: str, result: str):
        """显示命令执行结果"""
        tag = 'error' if "失败" in result else 'system'
        self._update_display(
            f"\n[命令执行] {command}\n结果：{result}\n{'='*50}\n",
            tag
        )

    def refresh_prompt(self):
        """刷新系统提示词"""
        self.system_prompt = TemplateManager.render(
            'system_prompt.jinja'
        )

    def load_template():
        env = os.getenv("APP_ENV", "dev")
        TemplateManager.render(
            f"system_prompt_{env}.jinja"
        )