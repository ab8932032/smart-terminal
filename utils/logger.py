# utils/logger.py
import logging
import os
from pathlib import Path
from typing import Optional

class Logger:
    _instance: Optional['Logger'] = None
    _initialized: bool = False

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.logger = logging.getLogger("smart_terminal")
            self._configure_logger()
            self._initialized = True

    def _configure_logger(self):
        """配置日志记录器"""
        base_dir = Path(__file__).parent.parent
        log_dir = base_dir / "logs"
        log_dir.mkdir(exist_ok=True)

        # 基础配置
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '[%(asctime)s] %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        # 文件处理器（按天轮转）
        file_handler = logging.FileHandler(log_dir / "app.log", encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        # 避免重复添加处理器
        if not self.logger.handlers:
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """获取日志记录器"""
        logger = self.logger.getChild(name) if name else self.logger
        # 添加exception方法支持
        logger.exception = self._enhanced_exception(logger)
        return logger

    def _enhanced_exception(self, logger: logging.Logger):
        """增强的异常记录方法"""
        def wrapper(msg, *args, exc_info=True, **kwargs):
            logger.error(msg, *args, exc_info=exc_info, **kwargs)
        return wrapper

# 模块级访问函数
def get_logger(name: Optional[str] = None) -> logging.Logger:
    return Logger().get_logger(name)