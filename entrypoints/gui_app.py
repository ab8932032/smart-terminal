from core.event_bus import EventBus
from core.process_controller import ProcessController
from core.retrieval_service import RetrievalService
from services.command_processor import CommandProcessor
from services.session_manager import SessionManager
from core.qa_engine import QAEngine
from utils.config_loader import ModelConfig, DBConfig
from utils.template_manager import TemplateManager


def launch_gui():
    # 加载配置文件
    config = ModelConfig.load()
    dbconfig = DBConfig.load()

    # 初始化核心组件
    event_bus = EventBus()
    session_manager = SessionManager(config)
    command_processor = CommandProcessor()
    
    template_manager = TemplateManager()  # 初始化模板管理器

    # 根据配置选择模型适配器
    model_provider = config.get("model_providers", {})
    enabled_model = next((v for k, v in model_provider.items() if v.get("enabled", False)), None)
    if not enabled_model:
        raise RuntimeError("No enabled model provider in config")
    model_adapter_path = enabled_model['adapter']
    module_path, class_name = model_adapter_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    ModelAdapterClass = getattr(module, class_name)
    model_adapter = ModelAdapterClass(enabled_model,event_bus)

    # 根据配置选择向量数据库适配器
    db_provider = dbconfig.get("db_providers", {})
    enabled_db = next((v for k, v in db_provider.items() if v.get("enabled", False)), None)
    if not enabled_db:
        raise RuntimeError("No enabled db provider in config")
    db_adapter_path = enabled_db['adapter']
    module_path, class_name = db_adapter_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    DBAdapterClass = getattr(module, class_name)
    db_adapter = DBAdapterClass(enabled_db)
    
    # 初始化检索服务
    retrieval_service = RetrievalService(db_adapter,enabled_db)

    # 初始化模板管理器
    template_manager = TemplateManager()

    # 初始化问答引擎
    qa_engine = QAEngine(
        model_adapter=model_adapter,
        retrieval_service=retrieval_service,
        template_manager=template_manager)
    
    # 创建流程控制器
    process_controller = ProcessController(
        event_bus=event_bus,
        qa_engine=qa_engine,
        command_processor=command_processor,
        session_manager=session_manager
    )

    # 动态加载前端类
    frontend_config = config.get("frontend_providers", {})
    enabled_frontends = [v for k, v in frontend_config.items() if v.get("enabled")]
    if not enabled_frontends:
        raise RuntimeError("No enabled frontend provider in config")
    adapter = enabled_frontends[0]
    # 动态导入前端类
    module_path, class_name = adapter['adapter'].rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    FrontendClass = getattr(module, class_name)  # 动态获取类 ·

    # 初始化前端
    frontend = FrontendClass(
        event_bus=event_bus,
        session_manager=session_manager,
        config = adapter
    )

    # 启动主循环
    frontend.start()
    
if __name__ == "__main__":
    launch_gui()