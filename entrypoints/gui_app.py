import asyncio
import os

from core.event_bus import EventBus
from core.process_controller import ProcessController
from core.retrieval_service import RetrievalService
from services.command_processor import CommandProcessor
from services.session_manager import SessionManager
from core.qa_engine import QAEngine
from utils.config_loader import ModelConfig, ProcessConfig, DBConfig
from utils.template_manager import TemplateManager
from utils.logger import get_logger

logger = get_logger(__name__)

def launch_gui():


    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
    # 加载配置文件
    logger.info("加载配置文件...")
    config = ModelConfig.load()
    process_config = ProcessConfig.load()  # 加载 process_config
    db_config = DBConfig.load()  # 加载 process_config
    logger.info("配置文件加载成功。")

    # 初始化核心组件
    logger.info("初始化核心组件...")
    event_bus = EventBus()
    session_manager = SessionManager(config)
    command_processor = CommandProcessor()
    template_manager = TemplateManager()  # 初始化模板管理器
    logger.info("核心组件初始化成功。")

    # 根据配置选择模型适配器
    logger.info("选择模型适配器...")
    model_provider = config.get("model_providers", {})
    enabled_model = next((v for k, v in model_provider.items() if v.get("enabled", False)), None)
    if not enabled_model:
        logger.error("配置中未找到启用的模型提供者")
        raise RuntimeError("No enabled model provider in config")
    model_adapter_path = enabled_model['adapter']
    module_path, class_name = model_adapter_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    ModelAdapterClass = getattr(module, class_name)
    model_adapter = ModelAdapterClass(enabled_model, event_bus)
    logger.info(f"已选择并初始化模型适配器 {model_adapter_path}。")

    # 根据配置选择向量数据库适配器
    logger.info("选择数据库适配器...")
    db_provider = db_config.get("db_providers", {})  # 获取 db_config
    enabled_db = next((v for k, v in db_provider.items() if v.get("enabled", False)), None)
    if not enabled_db:
        logger.error("配置中未找到启用的数据库提供者")
        raise RuntimeError("No enabled db provider in config")
    db_adapter_path = enabled_db['adapter']
    module_path, class_name = db_adapter_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    DBAdapterClass = getattr(module, class_name)
    db_adapter = DBAdapterClass(enabled_db)
    logger.info(f"已选择并初始化数据库适配器 {db_adapter_path}。")
    
    # 初始化检索服务
    logger.info("初始化检索服务...")
    retrieval_service = RetrievalService(db_adapter)
    logger.info("检索服务初始化成功。")

    # 初始化问答引擎
    logger.info("初始化问答引擎...")
    qa_engine = QAEngine(
        model_adapter=model_adapter,
        template_manager=template_manager,
        event_bus=event_bus)
    logger.info("问答引擎初始化成功。")
    
    # 创建流程控制器
    logger.info("创建流程控制器...")
    process_controller = ProcessController(
        event_bus=event_bus,
        qa_engine=qa_engine,
        retrieval_service=retrieval_service,
        command_processor=command_processor,
        session_manager=session_manager,
        process_config=process_config  # 修改: 传递 process_config
    )
    logger.info("流程控制器创建成功。")

    # 动态加载前端类
    logger.info("加载前端类...")
    frontend_config = config.get("frontend_providers", {})
    enabled_frontends = [v for k, v in frontend_config.items() if v.get("enabled")]
    if not enabled_frontends:
        logger.error("配置中未找到启用的前端提供者")
        raise RuntimeError("No enabled frontend provider in config")
    adapter = enabled_frontends[0]
    # 动态导入前端类
    module_path, class_name = adapter['adapter'].rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    FrontendClass = getattr(module, class_name)  # 动态获取类
    logger.info(f"前端类 {adapter['adapter']} 加载成功。")

    # 初始化前端
    logger.info("初始化前端...")
    frontend = FrontendClass(
        event_bus=event_bus,
        session_manager=session_manager,
        config=adapter
    )
    logger.info("前端初始化成功。")

    # 启动主循环
    logger.info("启动主循环...")
    frontend.start()  # 新增异步启动接口
    logger.info("主循环启动成功。")
    
if __name__ == "__main__":
    launch_gui()  # 用事件循环运行异步主函数