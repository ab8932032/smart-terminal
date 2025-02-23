# core/qa_engine.py
import json
import asyncio
from typing import Dict, List, Optional
from transformers import pipeline, TextStreamer, BitsAndBytesConfig
from jinja2 import Template
import torch
import logging
from utils.logger import get_logger
from retrieval_service import RetrievalService
from utils.template_manager import TemplateManager


logger = get_logger(__name__)

class QAEngine:
    def __init__(
        self, 
        model_config: Dict,
        template_manager: Optional['TemplateManager'] = None,
    ):
        """
        初始化问答引擎
        
        :param model_config: 模型配置字典
        :param retrieval_service: 检索服务实例
        """
        self.model_config = model_config
        self.retrieval_service =  RetrievalService(template_manager)
        
        # 初始化模型
        self.model, self.streamer = self._load_model()
        
        # 生成参数配置
        self.generation_params = {
            "max_new_tokens": model_config.get("max_new_tokens", 8192),
            "do_sample": model_config.get("do_sample", True),
            "temperature": model_config.get("temperature", 0.7),
            "num_return_sequences": model_config.get("num_return_sequences", 1),
            "return_full_text": False
        }

    def _load_model(self) -> tuple:
        """加载量化模型和流式处理器"""
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.benchmark = True

            quant_config = BitsAndBytesConfig(
                load_in_4bit=self.model_config['quantization']['enabled'],
                bnb_4bit_quant_type=self.model_config['quantization']['type'],
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True
            )

            model = pipeline(
                "text-generation",
                model=self.model_config['model_name'],
                device_map="auto",
                model_kwargs={
                    "quantization_config": quant_config,
                    "attn_implementation": self.model_config['model_args']['attn_implementation']
                }
            )

            streamer = TextStreamer(
                model.tokenizer, 
                skip_prompt=True, 
                skip_special_tokens=True
            )

            logger.info(f"模型加载成功，最大序列长度：{model.tokenizer.model_max_length}")
            return model, streamer

        except Exception as e:
            logger.error(f"模型加载失败: {str(e)}")
            raise RuntimeError("无法初始化问答模型") from e

    def _build_messages(self, context: Dict) -> List[Dict]:

        return [
            {
                "role": "system",
                "content": TemplateManager.render(
                    "system_prompt.jinja",
                    {  # 修正字典语法
                        "rules": context.get("rules", {}),
                        "response_format": context.get("response_format", {})
                    }
                )
            },
            {
                "role": "user",
                "content": TemplateManager.render(
                    "user_prompt.jinja",
                    {
                        "question": context["question"],
                        "search_results": json.dumps(context["search_results"], ensure_ascii=False)
                    }
                )
            }
        ]

    async def generate_answer(
        self, 
        question: str,
        timeout: int = 300
    ) -> Dict:
        """
        生成问答结果
        
        :param question: 用户问题
        :param timeout: 超时时间（秒）
        :return: 包含结果和状态的字典
        """
        try:
            # 执行检索
            search_results = await self.retrieval_service.hybrid_search(
                query=question,
                top_k=self.model_config.get("search_top_k", 5)
            )
            
            # 构建上下文
            context = {
                "question": question,
                "search_results": [
                    {
                        "filename": res['filename'],
                        "text": res['text'],
                        "score": round(res['score'], 2)
                    } 
                    for res in search_results
                ],
                "response_format": TemplateManager.render("response_format.jinja")
            }

            # 构建消息
            messages = self._build_messages(context)
            
            # 异步生成
            return await asyncio.wait_for(
                self._async_generate(messages),
                timeout=timeout
            )

        except asyncio.TimeoutError:
            logger.warning("问答生成超时")
            return {"status": "timeout", "answer": "生成超时，请简化问题重试"}
        except Exception as e:
            logger.error(f"生成失败: {str(e)}")
            return {"status": "error", "answer": f"生成异常: {str(e)}"}

    async def _async_generate(self, messages: List[Dict]) -> Dict:
        """异步生成实现"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.model(
                messages,
                streamer=self.streamer,
                **self.generation_params
            )
        )
        
        return {
            "status": "success",
            "answer": result[0]['generated_text'],
            "metadata": {
                "model": self.model_config['model_name'],
                "tokens_used": len(result[0]['generated_tokens'])
            }
        }

    def update_generation_params(self, **kwargs):
        """动态更新生成参数"""
        valid_params = {
            k: v for k, v in kwargs.items() 
            if k in self.generation_params
        }
        self.generation_params.update(valid_params)
        logger.info(f"更新生成参数: {valid_params}")