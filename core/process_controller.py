# core/process_controller.py
import asyncio
import uuid
from datetime import datetime
from time import time
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

from core.event_bus import EventBus
from core.retrieval_service import RetrievalService
from utils.logger import get_logger
from core.events import EventType
from services.command_processor import CommandProcessor
from services.session_manager import SessionManager
from core.qa_engine import QAEngine
from utils.config_loader import ConfigLoader, ProcessConfig

logger = get_logger(__name__)

@dataclass
class PipelineContext:
    session_id: str
    question: str
    correlation_id: str = None
    task: Optional[asyncio.Task] = None  # 添加任务引用
    knowledge: list = field(default_factory=list)

class ProcessController:
    def __init__(
            self,
            event_bus: EventBus,
            qa_engine: QAEngine,
            command_processor: CommandProcessor,
            session_manager: SessionManager,
            retrieval_service: Optional[RetrievalService] = None,
            process_config: ProcessConfig = None  # 新增: 通过参数传递 process_config
    ):
        self.retrieval_service = retrieval_service
        self.event_bus = event_bus
        self.qa_engine = qa_engine
        self.command_processor = command_processor
        self.session_manager = session_manager
        self._active_tasks = set()
        
        self.process_config = process_config  # 修改: 使用传入的 process_config
        self._task_semaphore = asyncio.Semaphore(self.process_config.task_control().get("max_concurrent_tasks", 5))
    
        self._register_event_handlers()

    def _register_event_handlers(self):
        """注册事件处理器"""
        event_mapping = {
            EventType.USER_INPUT: self.handle_user_input,
            EventType.CLEAR_HISTORY: self.handle_clear_history,
            EventType.CANCEL_OPERATION: self.handle_cancel_operation,
            EventType.GENERATION_START: self.handle_generation_start,
            EventType.GENERATION_COMPLETE: self.handle_generation_complete,
            EventType.RETRIEVE_KNOWLEDGE: self.handle_retrieve_knowledge
        }

        for event_type, handler in event_mapping.items():
            self.event_bus.subscribe(event_type, handler)
    def handle_retrieve_knowledge(self, data: Dict):
        """显式处理知识检索请求"""
        self._retrieve_knowledge(PipelineContext(
            session_id=data["session_id"],
            question=data["question"]
        ))

    def handle_clear_history(self, data=None):
    
        # 需要同步清理会话
        self.session_manager.clear_history(data.get("session_id") if data else self.session_manager.get_current_session())
    async def handle_user_input(self, data: Dict[str, Any]):
        """处理用户输入主流程"""
        ctx = PipelineContext(
            session_id=self.session_manager.get_current_session(),
            question=data.get("text", "").strip()
        )

        if not ctx.question:
            return

        try:
            async with self._task_semaphore:
                async with asyncio.TaskGroup() as tg:
                    process_task = tg.create_task(self._process_input(ctx))
                    ctx.task = process_task
                    self._active_tasks.add(process_task)
                    process_task.add_done_callback(
                        lambda t: self._active_tasks.discard(t)
                    )
        except Exception as e:
            self._publish_error("input_processing", str(e), ctx.question)

    async def _process_input(self, ctx: PipelineContext):
        """输入处理流水线"""
        try:
            sanitized = self.command_processor.sanitize_input(ctx.question)

            if self.command_processor.is_dangerous_command(sanitized):
                await self._handle_command(sanitized, ctx)
            else:
                await self._handle_qa_flow(ctx)

        except asyncio.CancelledError:
            logger.info("Processing cancelled")
        except Exception as e:
            self._publish_error("processing", str(e), ctx.question)

    async def _handle_command(self, command: str, ctx: PipelineContext):
        """命令执行处理"""
        if self.command_processor.is_dangerous_command(command):
            self.event_bus.publish(EventType.SECURITY_ALERT, {
                "type": "dangerous_command",
                "command": command,
                "session_id": ctx.session_id
            })
            return

        try:
            result = await asyncio.wait_for(
                self.command_processor.execute_async(command),
                timeout=self.process_config.task_control().get("command_timeout", 30)
            )

            event_type = EventType.COMMAND_SUCCESS if result["status"] == "success" else EventType.COMMAND_ERROR
            self.event_bus.publish(event_type, {
                **result,
                "session_id": ctx.session_id
            })

        except asyncio.TimeoutError:
            self._publish_error("command_timeout", "Command execution timed out", command)

    async def _handle_qa_flow(self, ctx: PipelineContext):
        """问答流程处理"""
        ctx.correlation_id = str(uuid.uuid4())
        try:
            async with asyncio.TaskGroup() as tg:
                # 创建并自动管理任务
                pipeline_task = tg.create_task(self._execute_qa_pipeline(ctx))
                ctx.task = pipeline_task  # 建立反向引用
                self._active_tasks.add(pipeline_task)
                pipeline_task.add_done_callback(
                    lambda t: self._active_tasks.discard(t)
                )
            # 任务完成后自动移除
            self._active_tasks.discard(pipeline_task)
    
        except asyncio.CancelledError:
            logger.info(f"QA flow cancelled: {ctx.correlation_id}")
            raise
        except ExceptionGroup as eg:
            for e in eg.exceptions:
                self._publish_error("qa_flow", str(e), ctx.question)

    async def _execute_qa_pipeline(self, ctx: PipelineContext):
        """封装完整的QA处理流水线"""
        # 保存用户提问

        summary = self.retrieval_service.vectordb.text_processor.summarize_text(ctx.question)
        self.session_manager.add_message(
            ctx.session_id,
            "user",
            ctx.question,
            thought="",
            summary=summary,
            metadata={"correlation_id": ctx.correlation_id}
        )
    
        # 知识检索
        knowledge = await self._retrieve_knowledge(ctx)
        ctx.knowledge = self._enrich_knowledge(knowledge)  # 新增知识增强处理

    # 生成响应
       
        await self._generate_response(ctx)

    def _enrich_knowledge(self, raw_knowledge: list) -> list:
        # 1. 添加时效性过滤
        current_year = datetime.now().year
        filtered = [k for k in raw_knowledge
                    if k.get('timestamp', current_year) >= current_year - 2]
    
        # 2. 添加来源可信度加权
        source_weights = self.process_config.get("source_weights", {}) 
        for item in filtered:
            item['weight'] = source_weights.get(item['source'], 1.0)
            item['content'] = ''.join(f"文件名:” {item['filename']}“ , 文件内容: ”{item['text']}“")
    
        # 3. 按相关性+时效性综合排序
        return sorted(filtered,
                      key=lambda x: (x['score'] * x['weight']),
                      reverse=True)
    def _filter_knowledge(self, results: list) -> list:
        """修复后的知识过滤"""
        for item in results:
            item['source'] ="local_database"
        return results
    
    async def _retrieve_knowledge(self, ctx: PipelineContext) -> list:
        if not self.retrieval_service: 
            self._publish_error("retrieval_error", "VectorDB adapter not initialized")
            return []
        
        """知识检索处理"""
        try:
            # 通过服务层进行检索
            raw_results = await self.retrieval_service.hybrid_search(
                query=ctx.question,
                top_k=self.process_config.get("max_knowledge_results", 5)  # 修改: 使用 process_config 替代 db_config
            )

            return self._filter_knowledge(raw_results)

        except asyncio.TimeoutError:
            self._publish_error("retrieval_timeout", "Knowledge retrieval timed out", ctx.question)
            return []


    async def _generate_response(self, ctx: PipelineContext):
        """生成响应流"""
        try:
            messages = self.session_manager.get_history(
                ctx.session_id,
                self.process_config.get("max_history_messages", 5))
            
                
            response_stream = self.qa_engine.generate_response(
                question=ctx.question,
                session_id=ctx.session_id,
                knowledge=ctx.knowledge,
                correlation_id=ctx.correlation_id,
                dialog_history=messages,
                stream=True  # 添加流式开关
            )

            async for chunk in response_stream:
                self._process_response_chunk(chunk, ctx)

        except Exception as e:
            self._publish_error("response_generation", str(e), ctx.question)

    def _process_response_chunk(self, chunk: Dict, ctx: PipelineContext):
        if not isinstance(chunk, dict):
            raise ValueError(f"无效的响应块类型: {type(chunk)}")
        # 新增安全过滤
        chunk["content"] = self.command_processor.filter_response(
            chunk.get("content", "")
        )

        """处理响应分片"""
        valid_chunk = self._validate_chunk(chunk)
                            
        self.session_manager.append_chunk(ctx.session_id, valid_chunk)

        self.event_bus.publish(EventType.RESPONSE_CHUNK, {
            "chunk": valid_chunk,
            "session_id": ctx.session_id,
            "correlation_id": ctx.correlation_id
        })

    def _validate_chunk(self, chunk: Dict) -> Dict:
        """验证响应块有效性"""
        required_keys = ["content"]
        if not all(k in chunk for k in required_keys):
            raise ValueError("Invalid response chunk format")
        return chunk
    
    def _split_response(self, response: str) -> Tuple[str, str]:
        """分离思考过程和最终回答"""
        thought = ""
        final_answer = response
    
        # 查找<Think>标签内容
        think_start = response.find("<think>")
        think_end = response.find("</think>")
        if think_start != -1 and think_end != -1:
            thought = response[think_start+7:think_end].strip()
            final_answer = response[think_end+8:].strip()
        return thought, final_answer
    
    def handle_generation_start(self, data: Dict):
        """处理生成开始事件"""

        metadata = self._build_metadata(data)
        self.event_bus.publish(EventType.STREAM_START, {
            "type": "ai_response",
            "correlation_id": data.get("correlation_id", ""),
            "metadata" : metadata
        })
    def handle_generation_complete(self, data: Dict):
        """处理生成完成事件"""
        try:
            metadata = self._build_metadata(data)
            full_response = self._finalize_response(data["session_id"])
            thought, final_answer = self._split_response(full_response)

            self._save_response_to_session(
                session_id=data["session_id"],
                response=final_answer,
                thought=thought,
                metadata=metadata
            )

            self._publish_final_response(full_response, metadata)

        except KeyError as e:
            self._publish_error("metadata_error", f"Missing key: {str(e)}", data)

    def _build_metadata(self, data: Dict) -> Dict:
        """构建响应元数据"""
        return { 
            "model": data.get("model_name", "default_model"), 
            "generated_at": datetime.now().isoformat(),
            "start_time": data.get("start_time", 0),
            "response_time": data.get("response_time", 0), 
            "sources": data.get("sources", []),  
            "correlation_id": data.get("correlation_id", ""),
            "session_id": data.get("session_id", "unknown")
        }

    def _finalize_response(self, session_id: str) -> str:
        """组装最终响应"""
        buffer = self.session_manager.get_response_buffer(session_id)
        return "".join(chunk.get("content", "") for chunk in buffer)

    def _save_response_to_session(self, session_id: str, response: str, thought: str, metadata: Dict):
        """保存响应到会话"""


        summary = self.retrieval_service.vectordb.text_processor.summarize_text(response)
        self.session_manager.add_message(
            session_id,
            "assistant",
            content= response,
            thought = thought,
            summary = summary,
            metadata=metadata
        )
        self.session_manager.clear_response_buffer(session_id)

    def _publish_final_response(self, response: str, metadata: Dict):
        """发布最终响应事件"""
        self.event_bus.publish(EventType.STREAM_END, {
            "type": "ai_response",
            "content": response,
            "metadata": metadata
        })

    def handle_cancel_operation(self, data: Dict):
        """按会话取消任务"""
        target_session = data.get("session_id")
    
        remaining_tasks = set()
        for task in self._active_tasks:
            try:
                # 获取任务关联的session_id
                ctx = getattr(task, 'ctx', None)
                if ctx and ctx.session_id == target_session:
                    task.cancel()
                else:
                    remaining_tasks.add(task)
            except:
                remaining_tasks.add(task)
    
        self._active_tasks = remaining_tasks
    def _publish_error(self, stage: str, message: str, context: Any = None):
        """统一错误处理"""
        error_data = {
            "stage": stage,
            "message": message,
            "context": context if isinstance(context, (str, dict)) else str(context)  # 修改：增加对 context 类型的检查
        }
        logger.error(f"{stage} error: {message}")
        self.event_bus.publish(EventType.ERROR, error_data)
        
        
