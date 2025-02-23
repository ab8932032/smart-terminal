import asyncio
from typing import Dict, Any
from utils.logger import get_logger
from core.events import EventType
from services.command_processor import CommandProcessor
from services.session_manager import SessionManager
from core.qa_engine import QAEngine
from adapters.model.ollama_adapter import OllamaAdapter
from adapters.vectordb.milvus_adapter import MilvusAdapter
import time
from datetime import datetime

logger = get_logger(__name__)

class ProcessController:
    def __init__(
        self,
        event_bus,
        qa_engine: QAEngine,
        command_processor: CommandProcessor,
        session_manager: SessionManager,
        ollama_adapter: Optional[OllamaAdapter] = None,
        milvus_adapter: Optional[MilvusAdapter] = None
    ):
        self.event_bus = event_bus
        self.qa_engine = qa_engine
        self.command_processor = command_processor
        self.ollama = ollama_adapter
        self.milvus = milvus_adapter
        self._active_tasks = set()
        self.session_manager = session_manager

        # 注册所有事件处理器
        self._register_event_handlers()

    def _register_event_handlers(self):
        """注册所有事件处理函数"""
        handlers = {
            EventType.USER_INPUT: self.handle_user_input,
            EventType.KNOWLEDGE_RESULT: self.handle_knowledge_result,
            EventType.COMMAND_RESULT: self.handle_command_result,
            EventType.CLEAR_HISTORY: self.handle_clear_history,
            EventType.CANCEL_OPERATION: self.handle_cancel_operation,
            EventType.RETRIEVE_KNOWLEDGE: self.handle_retrieve_knowledge,
            EventType.GENERATION_COMPLETE: self.handle_generation_complete
        }

        for event_type, handler in handlers.items():
            self.event_bus.subscribe(event_type, handler)

    async def handle_user_input(self, data: Dict[str, Any]):
        """完整用户输入处理流水线"""
        try:
            # 状态更新
            self.event_bus.publish(EventType.STATUS_UPDATE, {
                "state": "processing",
                "operation": "user_input"
            })

            text = data.get("text", "").strip()
            if not text:
                return

            # 预处理阶段
            sanitized = await self.command_processor.sanitize_async(text)

            # 分流处理
            if self.command_processor.is_command(sanitized):
                await self._handle_command_flow(sanitized)
            else:
                await self._handle_qa_flow(sanitized)

        except Exception as e:
            logger.error(f"Input processing failed: {str(e)}")
            self.event_bus.publish(EventType.ERROR, {
                "stage": "input_processing",
                "message": str(e),
                "original_input": text
            })
        finally:
            self.event_bus.publish(EventType.STATUS_UPDATE, {"state": "idle"})

    async def _handle_command_flow(self, command: str):
        """命令执行完整流程"""
        # 安全检查
        if self.command_processor.is_dangerous(command):
            self.event_bus.publish(EventType.SECURITY_ALERT, {
                "type": "dangerous_command",
                "command": command
            })
            return

        # 执行命令
        self.event_bus.publish(EventType.COMMAND_START, {"command": command})
        try:
            result = await self.command_processor.execute_async(command)
            if result["status"] == "success":
                self.event_bus.publish(EventType.OUTPUT_UPDATE, {
                    "type": "command_result",
                    "content": result["output"]
                })
            else:
                self.event_bus.publish(EventType.COMMAND_ERROR, {
                    "command": command,
                    "error": result["error"]
                })
        except Exception as e:
            self.event_bus.publish(EventType.ERROR, {
                "stage": "command_execution",
                "message": str(e)
            })

    async def _handle_qa_flow(self, question: str):
        """问答处理完整流程"""
        task = asyncio.create_task(self._execute_qa_pipeline(question))
        self._active_tasks.add(task)
        task.add_done_callback(lambda t: self._active_tasks.remove(t))

    async def _execute_qa_pipeline(self, question: str):
        """问答处理流水线"""
        try:
            # 获取当前会话
            session_id = self.session_manager.get_current_session()

            # 保存用户提问
            self.session_manager.add_message(
                session_id,
                "user",
                question
            )
            
            # 知识检索
            knowledge = await self._retrieve_knowledge(question)

            # 流式生成响应
            await self._handle_streaming_response(question)

        except asyncio.CancelledError:
            logger.info("QA pipeline cancelled")
        except Exception as e:
            self.event_bus.publish(EventType.ERROR, {
                "stage": "qa_pipeline",
                "message": str(e)
            })

    async def _retrieve_knowledge(self, question: str) -> list:
        """知识检索处理"""
        future = asyncio.Future()

        def knowledge_handler(data):
            if not future.done():
                future.set_result(data)

        self.event_bus.subscribe(EventType.KNOWLEDGE_RESULT, knowledge_handler)
        try:
            self.event_bus.publish(EventType.RETRIEVE_KNOWLEDGE, {"question": question})
            return await asyncio.wait_for(future, timeout=5.0)
        finally:
            self.event_bus.unsubscribe(EventType.KNOWLEDGE_RESULT, knowledge_handler)

    async def _postprocess_response(self, response: Dict) -> Dict:
        """响应后处理"""
        # 添加溯源信息
        if "sources" not in response:
            response["sources"] = []

        # 安全过滤
        response["content"] = await self.command_processor.filter_response(
            response["content"]
        )
        return response

    def handle_knowledge_result(self, data: Dict):
        """处理知识检索结果"""
        try:
            results = data.get("results", [])
            filtered = sorted(results, key=lambda x: x['score'], reverse=True)[:3]
            self.event_bus.publish(EventType.KNOWLEDGE_FILTERED, {
                "original_query": data["question"],
                "results": filtered
            })
        except KeyError as e:
            self.event_bus.publish(EventType.ERROR, {
                "stage": "knowledge_processing",
                "message": f"Missing key in knowledge result: {str(e)}"
            })

    def handle_command_result(self, data: Dict):
        """处理命令执行结果"""
        if data["status"] == "success":
            self.event_bus.publish(EventType.OUTPUT_UPDATE, {
                "type": "command_success",
                "content": data["output"]
            })
        else:
            self.event_bus.publish(EventType.COMMAND_ERROR, {
                "command": data["command"],
                "error": data["error"]
            })

    def handle_clear_history(self, _=None):
        """处理历史记录清除"""
        self.qa_engine.clear_context()
        self.event_bus.publish(EventType.HISTORY_CLEARED)

    def handle_cancel_operation(self, _=None):
        """处理取消操作"""
        for task in self._active_tasks:
            if not task.done():
                task.cancel()
        self._active_tasks.clear()
        self.event_bus.publish(EventType.STATUS_UPDATE, {"state": "idle"})

    # 修正后的handle_generation_complete
    def handle_generation_complete(self, data: Dict):
        """处理生成完成事件"""
        session_id = None
        try:
            session_id = self.session_manager.get_current_session()
            full_response = "".join(
                self.session_manager.get_response_buffer(session_id)
            )
    
            metadata = {
                "model": "ollama/deepseek-r1",
                "generated_at": datetime.now().isoformat(),
                "response_time": time.time() - data["start_time"],
                "sources": data.get("sources", [])
            }
    
            self.session_manager.add_message(
                session_id,
                "assistant",
                full_response,
                metadata=metadata
            )
            self.session_manager.clear_response_buffer(session_id)
    
            self.event_bus.publish(EventType.OUTPUT_UPDATE, {
                "type": "ai_response",
                "content": full_response,
                "metadata": metadata,
                "session_id": session_id
            })
    
            self.event_bus.publish(EventType.STREAM_END, {
                "session_id": session_id,
                "status": "success"
            })
    
        except Exception as e:
            logger.error(f"生成完成处理失败: {str(e)}")
            if session_id:
                self.session_manager.clear_response_buffer(session_id)
                self.event_bus.publish(EventType.STREAM_END, {
                    "session_id": session_id,
                    "status": "error",
                    "error": str(e)
                })
            self.event_bus.publish(EventType.ERROR, {
                "stage": "generation_complete",
                "message": f"Finalization failed: {str(e)}"
            })

    async def _handle_streaming_response(self, question: str):
        """处理流式响应生成"""
        try:

            self.event_bus.publish(EventType.STREAM_START, {"question": question})
            # 获取当前会话历史
            session_id = self.session_manager.get_current_session()
            history = self.session_manager.get_history(session_id)
    
            # 发起流式请求
            async for chunk in self.ollama.chat(
                    messages=history,
                    stream=True
            ):
                # 实时更新响应
                self.event_bus.publish(EventType.RESPONSE_CHUNK, {
                    "chunk": chunk,
                    "session_id": session_id
                })
    
                # 实时保存到会话
                self.session_manager.append_chunk(session_id, chunk)

            self.event_bus.publish(EventType.STREAM_END, {"status": "success"})
        except Exception as e:
            logger.error(f"流式响应失败: {str(e)}")
            self.event_bus.publish(EventType.STREAM_END, {"status": "error"})