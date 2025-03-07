from typing import Dict, Any
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from core.event_bus import EventBus
from services.session_manager import SessionManager
from utils.config_loader import ModelConfig
from adapters.frontends.base_frontend import BaseFrontend
import json
import asyncio

class WebAPI(BaseFrontend):
    def __init__(self,
                 event_bus: EventBus,
                 session_manager: SessionManager,
                 config: Dict[str, Any]):
        self.app = FastAPI()
        self.active_connections = set()
        super().__init__(event_bus, session_manager, config)

    def _configure_base_styles(self):
        """Web API无需样式配置"""
        pass

    def _build_interface(self):
        """构建API路由和WebSocket"""
        # 配置中间件
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 定义数据模型
        class UserInput(BaseModel):
            text: str
            session_id: str = "default"

        # 注册路由
        @self.app.post("/api/command")
        async def handle_command(input: UserInput):
            """处理用户命令输入"""
            self.event_bus.publish("USER_INPUT", {
                "text": input.text,
                "session_id": input.session_id
            })
            return {"status": "processing"}

        # WebSocket路由
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_connections.add(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    # 处理客户端消息（如果需要）
            finally:
                self.active_connections.remove(websocket)

    def _setup_event_bindings(self):
        """绑定核心事件到WebSocket广播"""
        self.event_bus.subscribe("OUTPUT_UPDATE", self._broadcast_output)
        self.event_bus.subscribe("STATUS_UPDATE", self._broadcast_status)
        self.event_bus.subscribe("ERROR", self._broadcast_error)

    async def _broadcast(self, event_type: str, payload: dict):
        """通用WebSocket广播方法"""
        message = json.dumps({"type": event_type, "data": payload})
        for connection in self.active_connections:
            await connection.send_text(message)

    def _broadcast_output(self, data: dict):
        asyncio.create_task(self._broadcast("output", data))

    def _broadcast_status(self, data: dict):
        asyncio.create_task(self._broadcast("status", data))

    def _broadcast_error(self, data: dict):
        asyncio.create_task(self._broadcast("error", data))

    def start(self):
        """启动Web服务器"""
        uvicorn.run(
            self.app,
            host=self.config.get("host", "0.0.0.0"),
            port=self.config.get("port", 8000),
            log_level="info"
        )

    # ---------- 实现抽象方法 ----------
    def handle_output_update(self, data: dict):
        """处理输出更新（通过WebSocket广播）"""
        self._broadcast_output(data)

    def handle_status_update(self, data: dict):
        """处理状态更新（通过WebSocket广播）"""
        self._broadcast_status(data)

    def handle_error(self, data: dict):
        """处理错误（通过WebSocket广播）"""
        self._broadcast_error(data)

    def get_user_input(self) -> str:
        """Web API通过HTTP接口获取输入"""
        return ""  # 实际从HTTP请求中获取

    def clear_user_input(self):
        """Web前端自行处理输入清空"""
        pass

    def update_display(self, content: str, content_type: str = "text"):
        """通过WebSocket更新显示"""
        self._broadcast_output({"content": content, "type": content_type})

    def clear_display(self):
        """清空显示区域"""
        self._broadcast_output({"action": "clear"})