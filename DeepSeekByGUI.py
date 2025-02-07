import os
import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox, simpledialog
import requests
import json
import threading
import re
import subprocess
import platform
import datetime

# 常量配置
API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "deepseek-r1:7b"
COMMAND_PATTERN = re.compile(
    r'^```(?:bash|shell|cmd|sh|powershell)?\s*\n((?:.|\n)*?)\n```$', re.MULTILINE | re.IGNORECASE
)
DANGER_PATTERNS = [r'rm\s+-rf', r'del\s+/s', r'chmod\s+777', r'powercfg', r'shutdown', r'mkfs', r'dd\s+if=', r'^curl\s+', r'^wget\s+']

class CommandProcessor:
    @staticmethod
    def detect_commands(response):
        """精准识别命令块并提取有效命令"""
        return [re.split(r'\s+#|\s+//', line.strip())[0] for line in COMMAND_PATTERN.findall(response) if line.strip() and not re.match(r'^\s*#|//', line.strip())]

    @staticmethod
    def execute_command(command):
        """执行命令并返回结果"""
        try:
            if platform.system() == "Windows":
                command = CommandProcessor._adapt_windows_command(command)
            result = subprocess.run(
                ['powershell', '-Command', command] if platform.system() == "Windows" else ["bash", "-c", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=True
            )
            return result.stdout.strip() or "命令执行成功（无输出）"
        except Exception as e:
            return f"执行失败: {str(e)}"

    @staticmethod
    def _adapt_windows_command(command):
        """转换Linux命令到Windows"""
        conversions = {
            r'^cat\s+(.*)': 'type {}',
            r'^ls\s*(.*)': 'dir {}',
            r'^/(usr|etc)/': 'C:\\{}'
        }
        for pattern, replacement in conversions.items():
            if re.match(pattern, command):
                return re.sub(pattern, replacement, command)
        return command

    @staticmethod
    def is_dangerous_command(command):
        """检查命令是否危险"""
        return any(re.search(pattern, command, re.IGNORECASE) for pattern in DANGER_PATTERNS)

class ChatGUI:
    def __init__(self, master):
        self.master = master
        master.title("DeepSeek 智能终端")
        master.geometry("1000x800")
        
        # 样式配置
        self.style = ttk.Style()
        self._configure_styles()
        
        # 界面布局
        self._create_widgets()
        self.is_responding = False
        # 添加对话历史记录
        self.conversation_history = []
        self.conversation_history.append({"role": "system", "content": "你是一个智能终端，请根据用户的指令执行命令并返回结果。如果有信息不全的，请提示用户补充更多你需要的信息"})

        # 初始化文件路径
        self._init_file_path()
        
        self._update_display(f"我是一个智能终端，请开始你的提问...\n\n\n", 'system')

    def _init_file_path(self):
        """初始化文件路径，以当前日期时间为名字"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file_path = f"DeepSeekR1History_{timestamp}.txt"

    def _save_to_file(self, text):
        """将问答结果保存到本地文件"""
        with open(self.file_path, 'a', encoding='utf-8') as file:
            file.write(text)

    def _get_ai_response(self, prompt):
        """获取AI响应（适配多轮对话API）"""
        messages = self.conversation_history.copy()
        messages.append({"role": "user", "content": prompt})
        prompt_str = json.dumps(messages, ensure_ascii=False)

        data = {
            "model": MODEL_NAME,
            "prompt": prompt_str,
            "stream": True,
            "temperature": 0.7
        }

        try:
            response = requests.post(API_URL, json=data, stream=True)
            response.raise_for_status()
            full_response = []
            self._update_display(f"智能终端：\n", 'system')
            for line in response.iter_lines():
                if line:
                    try:
                        json_data = json.loads(line.decode('utf-8'))
                        if 'response' in json_data:
                            self._stream_char(json_data['response'])
                            full_response.append(json_data['response'])
                        if json_data.get('done', False):
                            final_response = ''.join(full_response)
                            self._process_commands(final_response)
                    except json.JSONDecodeError:
                        self._show_error("接收到无效响应格式")

            self._stream_char("\n=========================================================================================================================\n")
            final_response = ''.join(full_response)
            self._process_commands(final_response)
            self.conversation_history.append({"role": "user", "content": prompt})
            self.conversation_history.append({"role": "assistant", "content": final_response})
            self._save_to_file("user:\n"+prompt+"\n")
            self._save_to_file("assistant:\n"+final_response+"\n=========================================================================================================================\n")
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

    def send_message(self):
        """处理用户发送消息"""
        if self.is_responding:
            return
            
        user_text = self.input_area.get("1.0", tk.END).strip()
        if not user_text:
            return
            
        self.clear_input()
        self._update_display(f"用户：\n", 'system')
        self._update_display(f"{user_text}\n\n", 'user')
        self.is_responding = True

        threading.Thread(target=self._get_ai_response, args=(user_text,), daemon=True).start()

    def clear_input(self):
        """清空输入框"""
        self.input_area.delete("1.0", tk.END)
        self.input_area.focus_set()

    def _process_commands(self, response):
        """处理响应中的命令"""
        if commands := CommandProcessor.detect_commands(response):
            self.master.after(0, self._confirm_command_execution, commands, response)

    def _confirm_command_execution(self, commands, context):
        """确认命令执行"""
        cmd_list = "\n".join([f"{i+1}. {cmd}" for i, cmd in enumerate(commands)])
        choice = simpledialog.askinteger(
            "命令检测",
            f"发现 {len(commands)} 个潜在命令\n\n上下文摘要：{context[:150]}...\n\n{cmd_list}\n\n输入要执行的命令编号（0取消）：",
            parent=self.master,
            minvalue=0,
            maxvalue=len(commands)
        )
        
        if choice and 0 < choice <= len(commands):
            if CommandProcessor.is_dangerous_command(commands[choice-1]):
                self._show_error("检测到危险命令，已阻止执行")
            else:
                self._execute_command(commands[choice-1])

    def _execute_command(self, command):
        """执行命令并显示结果"""
        def execution_thread():
            self._update_status(f"正在执行命令: {command[:30]}...")
            result = CommandProcessor.execute_command(command)
            tag = 'error' if "失败" in result else 'system'
            self._update_display(f"\n[命令执行] {command}\n结果：{result}\n{'='*50}\n", tag)
            self._update_status("就绪")
        
        threading.Thread(target=execution_thread, daemon=True).start()

    def _stream_char(self, char):
        """实时流式显示字符"""
        self.master.after(0, self._update_display, char, 'assistant', False)
    
    def _update_status(self, message):
        """更新状态栏"""
        self.status_bar.config(text=message)

    def _show_error(self, message):
        """显示错误信息"""
        self._update_display(f"\n⚠️ {message}\n", 'error')

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

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatGUI(root)
    root.mainloop()