# -*- coding: utf-8 -*-
import asyncio
import re
import subprocess
import platform
# 常量配置
API_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "deepseek-r1:7b"
#MODEL_NAME= "qwen2.5"
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
    def execute_command(command: str) -> str:
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

    async def execute_async(self, command: str) -> dict:
        try:
            result = await asyncio.to_thread(self.execute_command, command)
            return {"status": "success", "output": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
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

    def sanitize_input(self, text: str) -> str:
        """增强型输入清洗"""
        # 移除注释
        text = re.sub(r'#.*', '', text)
        # 标准化空格
        text = re.sub(r'\s+', ' ', text)

        # 过滤特殊字符（保留常见符号）
        text = re.sub(r'[^\w\s\-_@$%&*]', '', text)
        # 过滤特殊字符
        return text.strip()

    @staticmethod
    def filter_response(content: str) -> str:
        """同步过滤危险内容"""
        danger_patterns = [
            r'rm -rf', r'del /s',
            r'chmod 777', r'passwd',
            r'^curl\s+', r'^wget\s+'
        ]
        for pattern in danger_patterns:
            content = re.sub(
                pattern,
                '[BLOCKED]',
                content,
                flags=re.IGNORECASE
            )
        return content

    async def filter_response_async(self, content: str) -> str:
        """异步安全过滤"""
        return await asyncio.to_thread(
            self.filter_response,
            content
        )
