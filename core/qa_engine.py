
import asyncio
from datetime import datetime
from typing import Dict, List, AsyncGenerator, Any
from utils.logger import get_logger
from core.events import EventType
from core.retrieval_service import RetrievalService
from utils.template_manager import TemplateManager
from adapters.model.base_model_adapter import BaseModelAdapter

logger = get_logger(__name__)

class QAEngine:
    def __init__(
            self,
            model_adapter: BaseModelAdapter,
            retrieval_service: RetrievalService,
            template_manager: TemplateManager
    ):
        """
        问答引擎服务
        :param model_adapter: 模型适配器实例
        :param retrieval_service: 检索服务实例
        :param template_manager: 模板管理实例
        """
        self.model_adapter = model_adapter
        self.retrieval_service = retrieval_service
        self.template_manager = template_manager
        required_templates = ['system_prompt.jinja', 'user_prompt.jinja']
        for tpl in required_templates:
            if not self.template_manager.template_exists(tpl):
                logger.error(f"构建提示词时发生错误,关键模板缺失: {str(tpl)}")
                raise

    # 添加块处理方法
    @staticmethod
    def _format_chunk(content: str) -> Dict[str, Any]:
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
            knowledge: List[Dict],
            stream: bool = False
    ) -> AsyncGenerator[Dict, None]:
        """
        生成问答响应（支持流式）
        :param knowledge: 
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
    
            # 构建提示词
            messages = self._build_prompt_messages(question, knowledge)

            chat_generator = await self.model_adapter.chat(  # 添加await获取生成器
                messages=messages,
                stream=stream
            )
            # 流式生成
            async for raw_chunk in chat_generator:
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
            yield self._format_chunk("生成响应时发生错误")
    def _build_prompt_messages(self, question: str, search_results: List[Dict]) -> List[Dict]:
        try:
            # 添加知识可信度提示
            knowledge_with_credibility = [
                f"[来源：{res.get('source','未知')} 可信度：{res.get('weight',1.0):.1f}] {res.get('content','')}"
                for res in search_results
            ]
        
            # 更新模板渲染逻辑
            user_prompt = self.template_manager.render(
                "user_prompt.jinja",
                {
                    "question": question,
                    "knowledge": "\n".join(knowledge_with_credibility)  # 结构化知识
                }
            )
            
            """构建提示词消息"""
            system_prompt = self.template_manager.render("system_prompt.jinja",context={})
    
            return [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        except Exception as e:
            logger.error(f"构建提示词时发生错误: {str(e)}")
            raise e