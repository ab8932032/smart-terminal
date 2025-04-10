
import asyncio
from datetime import datetime
from typing import Dict, List, AsyncGenerator, Any

from core.event_bus import EventBus
from utils.logger import get_logger
from core.events import EventType
from utils.template_manager import TemplateManager
from adapters.model.base_model_adapter import BaseModelAdapter

logger = get_logger(__name__)

class QAEngine:

    def __init__(
            self,
            model_adapter: BaseModelAdapter,
            template_manager: TemplateManager,
            event_bus: EventBus
    ):
        """
        问答引擎服务
        :param model_adapter: 模型适配器实例
        :param template_manager: 模板管理实例
        """
        self.model_adapter = model_adapter
        self.template_manager = template_manager
        self.event_bus = event_bus
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
            "start_time": datetime.now().isoformat()
        }
    
    async def generate_response(
            self,
            question: str,
            session_id: str,
            knowledge: List[Dict],
            correlation_id: str,
            dialog_history: List[Dict],
            stream: bool = False
    ) -> AsyncGenerator[Dict, None]:
        """
        生成问答响应（支持流式）
        """
        logger.info(f"开始生成响应: session_id={session_id}, question={question}")  # 新增日志
        start_time = datetime.now().isoformat()
        sources = [item.get("source", "unknown") for item in knowledge]
        try:
            
            self.event_bus.publish(EventType.GENERATION_START, {
                "question": question,
                "session_id": session_id,
                "start_time": start_time,
                "model_name": self.model_adapter.config.get("model_name"),
                "sources": list(set(sources)),
                "correlation_id" : correlation_id,
            })

            messages = self._build_prompt_messages(question, knowledge,dialog_history)

            chat_generator = self.model_adapter.chat(
                messages=messages,
                stream=stream
            )
            async for raw_chunk in chat_generator:
                formatted_chunk = self._format_chunk(raw_chunk)
                logger.debug(f"生成响应块: {formatted_chunk}")  # 新增日志
                yield formatted_chunk

            logger.info(f"响应生成完成: session_id={session_id}")  # 新增日志

            end_time = datetime.now().isoformat()
            self.event_bus.publish(EventType.GENERATION_COMPLETE, {
                "session_id": session_id,
                "status": "success",
                "start_time": start_time,
                "model_name": self.model_adapter.config.get("model_name"),
                "response_time": end_time,
                "sources": list(set(sources)),
                "correlation_id" : correlation_id,
            })

        except asyncio.CancelledError:
            logger.info("生成任务被取消")

            end_time = datetime.now().isoformat()
            self.event_bus.publish(EventType.GENERATION_COMPLETE, {
                "session_id": session_id,
                "status": "cancelled",
                "start_time": start_time,
                "model_name": self.model_adapter.config.get("model_name"),
                "response_time": end_time,
                "sources": list(set(sources)),
                "correlation_id" : correlation_id,
            })
        except Exception as e:
            logger.error(f"生成失败: {str(e)}")  # 新增日志
            self.event_bus.publish(EventType.ERROR, {
                "stage": "response_generation",
                "message": str(e),
            })
    def _build_prompt_messages(self, question: str, search_results: List[Dict],dialog_history: List[Dict]) -> List[Dict]:
        try:
            # 添加知识可信度提示
            knowledge_with_credibility = [
                f"[来源：{res.get('source','未知')} 可信度：{res.get('weight',1.0):.1f} 数据：{res.get('content','')}]"
                for res in search_results
            ]
        
            # 更新模板渲染逻辑
            user_prompt = self.template_manager.render(
                "user_prompt.jinja",
                {
                    "question": question,
                    "knowledge": search_results  # 结构化知识
                }
            )
            
            """构建提示词消息"""
            system_prompt = self.template_manager.render("system_prompt.jinja",context={})
            messages = [{"role": "system", "content": system_prompt}]

            for msg in dialog_history[:-1]:
                summary = msg.get("summary",'')
                messages.append({"role": msg.get("role"), "content": summary})
            messages.append({"role": "user", "content": user_prompt})
            
            return messages
        
        except Exception as e:
            logger.error(f"构建提示词时发生错误: {str(e)}")
            raise e