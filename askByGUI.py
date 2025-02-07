import tkinter as tk
from tkinter import ttk, scrolledtext,filedialog
import threading
import subprocess
import sys
import re
import platform

# 常量配置
API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "deepseek-r1:7b"
COMMAND_PATTERN = re.compile(
    r'^```(?:bash|shell|cmd|sh|powershell)?\s*\n'  # 匹配代码块开始
    r'((?:.|\n)*?)'                                 # 捕获命令内容
    r'\n```$',                                      # 匹配代码块结束
    re.MULTILINE | re.IGNORECASE
)
DANGER_PATTERNS = [
    r'rm\s+-rf', r'del\s+/s', 
    r'chmod\s+777', r'powercfg', r'shutdown',
    r'mkfs', r'dd\s+if=', r'^curl\s+', r'^wget\s+'
]

class CommandProcessor:
    @staticmethod
    def detect_commands(response):
        """精准识别命令块并提取有效命令"""
        commands = []
        for code_block in COMMAND_PATTERN.findall(response):
            # 分割命令并清洗
            lines = code_block.split('\n')
            for line in lines:
                # 去除前后空白
                cleaned = line.strip()
                # 过滤空行和注释（支持#和//两种注释）
                if cleaned and not re.match(r'^\s*#|//', cleaned):
                    # 去除行内注释（支持#和//）
                    command = re.split(r'\s+#|\s+//', cleaned)[0]
                    commands.append(command)
        return commands

    @staticmethod
    def execute_command(command):
        """执行命令并返回结果"""
        try:
            # 跨平台处理
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
        for pattern in DANGER_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

class ChatGUI:
    def __init__(self, root):
        self.root = root
        self.master = root
        self.is_responding = True
        
        # 窗口配置
        root.title("智能对话系统")
        root.geometry("1280x720")
        
        # 初始化布局
        self.init_ui()
        
    def init_ui(self):
        # 标题栏
        self.status_bar = ttk.Label(
            self.master, 
            text="就绪", 
            style='Status.TLabel'
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 创建消息编辑框
        self.input_area = scrolledtext.ScrolledText(
            self.master,
            wrap=tk.WORD,
            width=100,
            height=20
        )
        self.input_area.pack(expand=True, fill="y")
        
        # 创建AI响应区域
        self.assistant_text = scrolledtext.ScrolledText(
            self.master,
            wrap=tk.WORD,
            width=100,
            height=30
        )
        self.assistant_text.pack(expand=True, fill="y")
        
        # 添加滚动条
        self.assistant_text.yview.set(" scrollbar ", " 1 ")
        self.input_area.yview.set(" scrollbar ", " -1 ")
        
        # 状态栏
        self.status_bar = ttk.Label(
            self.master, 
            text="就绪", 
            style='Status.TLabel'
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 配置UI布局
        self.create_ui_components()
        
    def create_ui_components(self):
        # 创建下拉菜单
        self.menubar = tk.Menu(self.master)
        self.master.config(menu=self.menubar)

        file_menu = tk.Menu(self.menubar)
        file_menu.add_command(label="新建")
        file_menu.add_command(label="打开")
        file_menu.add_command(label="保存")
        file_menu.add_command(label="另存为")
        file_menu.add_command(label="关闭")
        self.menubar.addMenu(file_menu)

        # 创建命令按钮
        button_frame = ttk.Frame(self.master)
        button_frame.pack(pady=5, padx=5)
        
        new_button = ttk.Button(
            button_frame,
            text="新建对话",
            command=self.new_dialog
        )
        new_button.pack(side=tk.LEFT)
        
        open_button = ttk.Button(
            button_frame,
            text="打开对话",
            command=lambda: self.open_dialog("open")
        )
        open_button.pack(side=tk.LEFT)
        
    def new_dialog(self):
        """新建一个对话框"""
        new_root = tk.Toplevel(self.master)
        new_root.title("智能对话系统")
        new_root.geometry("800x600")
        # 添加UI组件
        self.init_ui()
        new_root.mainloop()
        
    def open_dialog(self, command="open"):
        """打开保存的对话文件"""
        try:
            file_path = filedialog.askopenfilename(filetypes=[("文本文件", "*.txt")])
            if file_path:
                self.load_dialog(file_path, command)
        except Exception as e:
            print(f"Error opening file: {e}")
            
    def load_dialog(self, filename, command="load"):
        """加载对话文件"""
        try:
            with open(filename) as f:
                content = f.read()
                
            # 设置消息编辑框的内容
            self.input_area.delete("1.0", tk.END)
            self.input_area.insert(tk.END, content)
            
            # 处理命令
            if command == "load":
                self.process_commands()
        except Exception as e:
            print(f"Error loading file: {e}")
            
    def process_commands(self):
        """处理对话内容"""
        while True:
            message = self.input_area.get("1.0", tk.END)
            if not message:
                break
            self.master.after(0, self.process_message, message)
                
    def process_message(self, message):
        """处理用户的输入消息"""
        # 发送消息到AI server
        self.send_to_ai(message)
        
        # 显示AI回复
        self.assistant_text.delete("1.0", tk.END)
        response = subprocess.run(
            ["python", "ai_response.py"],
            input=message.encode('utf-8'),
            capture_output=True,
            text=True
        ).stdout
        
        self.assistant_text.insert(tk.END, response)
        
    def send_to_ai(self, message):
        """发送消息到AI server"""
        try:
            # 这里可以替换为实际的AI服务调用方式
            # 例如：网络请求、WebSocket等
            pass
            
        except Exception as e:
            print(f"Error sending message: {e}")
            
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatGUI(root)
    root.mainloop()