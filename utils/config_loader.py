import os
import yaml
from abc import abstractmethod, ABC
from pathlib import Path
from typing import Dict, Any

class ConfigLoader:
    @staticmethod
    def load_yaml(config_path: str) -> Dict[str, Any]:
        """
        加载YAML配置文件并解析环境变量占位符
        示例配置："""
        base_dir = Path(__file__).parent.parent / 'configs'  # 项目根目录
        full_path = base_dir / config_path
        

        with open(full_path, 'r', encoding='utf-8') as f:
            config_str = f.read()
            # 替换环境变量（支持默认值）
            config_str = ConfigLoader._replace_env_vars(config_str)
            return yaml.safe_load(config_str)

    @staticmethod
    def _replace_env_vars(config_str: str) -> str:
        import re
        pattern = re.compile(r'\$\{([^}]+)\}')
        
        def replace_match(match):
            var_def = match.group(1)
            var_name, _, default = var_def.partition(':')
            return os.getenv(var_name, default) if default else os.getenv(var_name, '')
            
        return pattern.sub(replace_match, config_str)

class BaseConfig(ABC):
    _config: Dict[str, Any] = None

    @classmethod
    def load(cls) -> 'BaseConfig':
        if not cls._config:
            cls._config = ConfigLoader.load_yaml(cls.config_path())
        return cls()


    @classmethod
    @abstractmethod
    def config_path(cls) -> str:
        pass

    @classmethod
    def get(cls, key_path: str, default=None) -> Any:
        keys = key_path.split('.')
        value = cls._config
        try:
            for key in keys:
                value = value[key]
            return value
        except KeyError:
            return default
class ModelConfig(BaseConfig):
    @classmethod
    def config_path(cls) -> str:
        return "model_config.yaml"
    
    @classmethod
    def model_providers(cls) -> Dict[str, Any]:
        return cls.get('model_providers', {})
    
    
    @classmethod
    def model_logging(cls) -> Dict[str, Any]:
        return cls.get('logging', {})


class DBConfig(BaseConfig):

    @classmethod
    def config_path(cls) -> str:
        return "db_config.yaml"

    @classmethod
    def milvus(cls) -> Dict[str, Any]:
        return cls.get('milvus', {})


class ProcessConfig(BaseConfig):

    @classmethod
    def config_path(cls) -> str:
        return "process_config.yaml"

    @classmethod
    def task_control(cls) -> Dict[str, Any]:
        return cls.get('task_control', {})