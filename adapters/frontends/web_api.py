from typing import Dict, Any
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from core.event_bus import EventBus
from core.events import EventType
from services.session_manager import SessionManager
from adapters.frontends.base_frontend import BaseFrontend
import json
import asyncio
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

class WebAPIFrontend(BaseFrontend):
    def __init__(self, event_bus: EventBus, session_manager: SessionManager, config: dict):
        self.app = FastAPI()
        self.templates = Jinja2Templates(directory="templates")
        self._setup_routes()
        self._response_buffer = ""
        self.in_think = False
        self.active_connections = set()
        super().__init__(event_bus, session_manager, config)

    def _configure_theme(self):
        """配置FastAPI主题"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _build_core_layout(self):
        """构建核心布局"""
        self.app.mount("/static", StaticFiles(directory="static"), name="static")

    def _setup_event_system(self):
        """设置事件系统"""
        pass

    def _setup_routes(self):
        """设置FastAPI路由"""
        @self.app.get("/", response_class=HTMLResponse)
        async def get_index(request: Request):
            return self.templates.TemplateResponse("index.html", {"request": request})

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_connections.add(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    self.handle_user_input()
                    self.event_bus.publish(EventType.USER_INPUT, {"input": data})
            except Exception as e:
                print(f"WebSocket error: {e}")
            finally:
                self.active_connections.remove(websocket)

    def start(self):
        """启动FastAPI服务"""
        uvicorn.run(self.app, host=self.config.get('host','127.0.0.0'), port=self.config.get('port',8080))

    async def handle_status_update(self, data: Dict[str, Any]):
        """处理状态更新事件"""
        status_map = {
            "processing": "🔄 处理中...",
            "idle": "✅ 就绪",
            "generating": "🤖 生成中"
        }
        status_text = status_map.get(data.get("state"), "❓ 未知状态")
        await self.update_display(status_text, content_type="status")

    async def handle_error(self, data: Dict[str, Any]):
        """处理错误事件"""
        error_msg = f"⛔ 错误 [{data.get('stage', '未知阶段')}]: {data.get('message', '未知错误')}"
        await self.update_display(error_msg, content_type="error")

    async def handle_security_alert(self, data: Dict[str, Any]):
        """处理安全警报事件"""
        pass

    async def update_display(self, content: str, content_type: str = "text"):
        """通过WebSocket更新显示内容"""
        for connection in self.active_connections:
            await connection.send_text(json.dumps({
                "type": content_type,
                "content": content
            }))

    def clear_display(self, data: dict[str, Any]):
        """清空显示内容"""
        pass

    def handle_user_input(self,user_input:str):
        """处理用户输入"""
        self.event_bus.publish(EventType.USER_INPUT, {"input": user_input})
        
    async def get_user_input(self) -> str:
        """获取用户输入"""
        # 等待WebSocket消息并返回用户输入
        while True:
            for conn in self.active_connections:
                try:
                    data = await conn.receive_text()
                    return data
                except Exception:
                    continue
