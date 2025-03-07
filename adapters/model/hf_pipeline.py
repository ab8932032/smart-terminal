# adapters/model/hf_pipeline.py
import asyncio
from typing import List, Dict, Optional, AsyncGenerator

import torch
from transformers import pipeline, AutoTokenizer, BitsAndBytesConfig

from adapters.model.base_model_adapter import BaseModelAdapter
from utils.logger import get_logger

logger = get_logger(__name__)

class HuggingFacePipeline(BaseModelAdapter):

    def __init__(self, config: dict,event_bus):
        """
        HuggingFace Pipeline适配器
        :param config: 配置加载器实例
        """
        super().__init__(config,event_bus)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.quant_config = self._init_quant_config()
        self.tokenizer = AutoTokenizer.from_pretrained(config['model_name'])
        self.pipeline = self._load_pipeline()

    def _init_quant_config(self) -> Optional[BitsAndBytesConfig]:
        """初始化量化配置"""
        if not self.config['quantization']['enabled']:
            return None

        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=self.config['quantization']['type'],
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True
        )

    def _load_pipeline(self):
        """加载生成管道"""
        try:
            return pipeline(
                "text-generation",
                model=self.config['model_name'],
                tokenizer=self.tokenizer,
                device_map="auto" if self.device == "cuda" else None,
                model_kwargs={
                    "quantization_config": self.quant_config,
                    "low_cpu_mem_usage": True
                }
            )
        except Exception as e:
            logger.error(f"模型加载失败: {str(e)}")
            raise

    async def chat(
            self,
            messages: List[Dict],
            stream: bool = False,
            **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        执行聊天请求
        :param messages: 消息历史 [{"role": "user", "content": "..."}]
        :param stream: 是否启用流式传输
        :return: 生成响应内容
        """
        try:
            input_text = self._build_input_text(messages)
            params = {**self.config['generation_params'], **kwargs}

            if stream:
                for response in await asyncio.to_thread(self.pipeline, input_text, **params):
                    if response and 'generated_text' in response[0]:
                        yield response[0]['generated_text']
                    else:
                        yield "生成失败，请检查模型配置"
            else:
                response = await asyncio.to_thread(self.pipeline, input_text, **params)
                if response and 'generated_text' in response[0]:
                    yield response[0]['generated_text']
                else:
                    yield "生成失败，请检查模型配置"
                    
        except Exception as e:
            logger.error(f"生成失败: {str(e)}")
            yield "生成失败，请检查模型配置"

    def _build_input_text(self, messages: List[Dict]) -> str:
        """构建输入文本"""
        return "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
