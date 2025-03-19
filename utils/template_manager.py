from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound


class TemplateManager:
    _instance = None
    env = None  # 提升为类变量

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def render(cls, template_name: str, context: dict) -> str:
        if not cls.env:
            cls.env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parent / "templates"))
        return cls.env.get_template(template_name).render(context)

    @classmethod
    def template_exists(cls, template_name: str) -> bool:
        """检查模板是否存在"""
        try:
            if not cls.env:
                print(f"Templates路径: {Path(__file__).resolve().parent.parent}")
                cls.env = Environment(loader=FileSystemLoader(Path(__file__).resolve().parent.parent / "templates"))
            cls.env.get_template(template_name)
            return True
        except TemplateNotFound:
            return False
    