# entrypoints/gui_app.py
import tkinter as tk
from core.event_bus import EventBus
from core.process_controller import ProcessController
from services.command_processor import CommandProcessor
from services.session_manager import SessionManager
from adapters.model.ollama_adapter import OllamaAdapter
from adapters.vectordb.milvus_adapter import MilvusAdapter
from core.qa_engine import QAEngine
from utils.config_loader import ModelConfig
from adapters.frontends.tkinter_gui import TkinterFrontend
from adapters.frontends.event_bindings import TkinterEventBinder


def launch_gui():
    # 加载配置文件
    config = ModelConfig.load()

    # 初始化核心组件
    event_bus = EventBus()
    session_manager = SessionManager(config)
    command_processor = CommandProcessor(config)
    ollama_adapter = OllamaAdapter(config)
    milvus_adapter = MilvusAdapter(config)

    # 初始化问答引擎
    qa_engine = QAEngine(
        ollama_adapter=ollama_adapter,
        milvus_adapter=milvus_adapter,
        config=config
    )

    # 创建流程控制器
    process_controller = ProcessController(
        event_bus=event_bus,
        qa_engine=qa_engine,
        command_processor=command_processor,
        ollama_adapter=ollama_adapter,
        milvus_adapter=milvus_adapter
    )

    # 初始化GUI前端
    root = tk.Tk()
    root.title("Smart Terminal")
    frontend = TkinterFrontend(
        master=root,
        event_bus=event_bus,
        session_manager=session_manager
    )

    # 注册全局事件绑定
    TkinterEventBinder.bind_all(root, event_bus)

    # 订阅核心显示事件
    event_bus.subscribe("OUTPUT_UPDATE", frontend.handle_output_update)
    event_bus.subscribe("STATUS_UPDATE", frontend.handle_status_update)
    event_bus.subscribe("SECURITY_ALERT", frontend.handle_security_alert)
    event_bus.subscribe("ERROR", frontend.handle_error)

    # 启动主循环
    root.mainloop()

if __name__ == "__main__":
    launch_gui()
