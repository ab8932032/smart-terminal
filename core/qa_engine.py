
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, AsyncGenerator, Any
from utils.logger import get_logger
from core.events import EventType
from core.retrieval_service import RetrievalService
from utils.template_manager import TemplateManager
from adapters.model.base_adapter import BaseModelAdapter
from utils.config_loader import ModelConfig

logger = get_logger(__name__)

class QAEngine:
    def __init__(
            self,
            model_adapter: BaseModelAdapter,
            retrieval_service: RetrievalService,
            template_manager: TemplateManager,
            config: ModelConfig = None
    ):
        """
        问答引擎服务
        :param model_adapter: 模型适配器实例
        :param retrieval_service: 检索服务实例
        :param template_manager: 模板管理实例
        :param config: 配置字典
        """
        self.model_adapter = model_adapter
        self.retrieval_service = retrieval_service
        self.template_manager = template_manager
        self.config = config.get('qa_engine',{})

    # 添加块处理方法
    def _format_chunk(self, content: str) -> Dict[str, Any]:
        """格式化响应块为标准结构"""
        return {
            "content": content,
            "is_final": False,
            "timestamp": datetime.now().isoformat()
        }
    
    async def generate_response(
            self,
            question: str,
            session_id: str,
            stream: bool = False
    ) -> AsyncGenerator[Dict, None]:
        """
        生成问答响应（支持流式）
        :param question: 用户问题
        :param session_id: 当前会话ID
        :param stream: 是否启用流式
        :yield: 响应内容块或完整响应
        """
        try:
            # 发布生成开始事件
            self.model_adapter.event_bus.publish(EventType.GENERATION_START, {
                "question": question,
                "session_id": session_id
            })
    
            # 执行知识检索
            search_results = await self._retrieve_knowledge(question)
    
            # 构建提示词
            messages = self._build_prompt_messages(question, search_results)
    
            # 流式生成
            async for raw_chunk in self.model_adapter.chat(...):
                formatted_chunk = self._format_chunk(raw_chunk)
                yield formatted_chunk
                # 实时发布响应块
                self.model_adapter.event_bus.publish(EventType.RESPONSE_CHUNK, {
                    "chunk": formatted_chunk,
                    "session_id": session_id
                })
    
            # 发布完成事件
            self.model_adapter.event_bus.publish(EventType.GENERATION_COMPLETE, {
                "session_id": session_id,
                "status": "success"
            })
    
        except asyncio.CancelledError:
            logger.info("生成任务被取消")
            self.model_adapter.event_bus.publish(EventType.GENERATION_COMPLETE, {
                "session_id": session_id,
                "status": "cancelled"
            })
        except Exception as e:
            logger.error(f"生成失败: {str(e)}")
            self.model_adapter.event_bus.publish(EventType.ERROR, {
                "stage": "response_generation",
                "message": str(e),
                "session_id": session_id
            })
            yield "生成响应时发生错误"
    
    async def _retrieve_knowledge(self, question: str) -> List[Dict]:
        """执行混合检索"""
        return await self.retrieval_service.hybrid_search(
            query=question,
            top_k=self.config.get("search_top_k", 5)
        )

    def _build_prompt_messages(self, question: str, search_results: List[Dict]) -> List[Dict]:
        """构建提示词消息"""
        system_prompt = self.template_manager.render(
            "system_prompt.jinja",
            {
                "response_rules": self.config.get("response_rules", {}),
                "allowed_commands": self.config.get("allowed_commands", [])
            }
        )

        user_prompt = self.template_manager.render(
            "user_prompt.jinja",
            {
                "question": question,
                "knowledge": json.dumps(search_results, ensure_ascii=False)
            }
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def update_config(self, new_config: Dict):
        """动态更新配置"""
        self.config.update(new_config)
        logger.info("问答引擎配置已更新")
        