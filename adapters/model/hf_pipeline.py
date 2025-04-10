import asyncio
import os
import time
from typing import List, Dict, Optional, AsyncGenerator

import torch
from transformers import (
    AutoTokenizer,
    BitsAndBytesConfig,
    AsyncTextIteratorStreamer,
    AutoModelForCausalLM,
)

from adapters.model.base_model_adapter import BaseModelAdapter
from utils.logger import get_logger
import threading

logger = get_logger(__name__)


class HuggingFacePipeline(BaseModelAdapter):
    def __init__(self, config: dict, event_bus):
        super().__init__(config, event_bus)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.quant_config = self._init_quant_config()
        self.tokenizer = AutoTokenizer.from_pretrained(config['model_name'])

        # 确保 pad_token 和 eos_token 一致（防止生成错误）
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.padding_side = "right"

        self.model = self._load_model()
        # 验证模板格式
        test_template = self._build_input_text(
            [{"role": "user", "content": "test"}]
        )

    def _init_quant_config(self) -> Optional[BitsAndBytesConfig]:
        if not self.config['quantization']['enabled']:
            return None
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=self.config['quantization']['type'],
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True
        )

    def _load_model(self):
        model = None
        try:
            model =  AutoModelForCausalLM.from_pretrained(
                self.config['model_name'],  # 支持本地路径（如：/path/to/local/model）
                device_map="auto" if self.device == "cuda" else None,
                quantization_config=self.quant_config,
                torch_dtype=torch.bfloat16,  # 显式设置计算类型
                low_cpu_mem_usage=True
            )
        except Exception as e:
            logger.error(f"模型加载失败: {str(e)}")
            raise

        print(model.config.sliding_window)         # 应为 None 或 4096 等数值
        print(model.config._attn_implementation)   # 应为 eager/sdpa/flash_attention_2
        return model

    async def chat(
            self,
            messages: List[Dict],
            stream: bool = False,
            **kwargs
    ) -> AsyncGenerator[str, None]:
        try:
            input_text = self._build_input_text(messages)
            inputs = self.tokenizer(
                input_text,
                return_tensors="pt",
                padding=True,
                truncation=True
            ).to(self.device)

            params = {
                **self.config['generation'],
                **kwargs,
               # "do_sample": True,
                "eos_token_id": self.tokenizer.eos_token_id,
                "pad_token_id": self.tokenizer.eos_token_id,
                "bos_token_id": self.tokenizer.bos_token_id
            }

            if stream:
                # 初始化异步队列
                queue = asyncio.Queue()
                streamer = AsyncTextIteratorStreamer(
                    self.tokenizer,
                    timeout=10.0,
                    skip_prompt=False,
                    skip_special_tokens=True
                )
                params["streamer"] = streamer

                # 启动生成线程
                generate_thread = threading.Thread(target=lambda: self.model.generate(**inputs, **params), daemon=True)
                generate_thread.start()
                try:
                    generated_text = ""
                    assistant_marker = "<｜Assistant｜>"
                    async for token in streamer:
                        generated_text += token
                        # 定位Assistant标记位置
                        last_assistant_pos = generated_text.rfind(assistant_marker)
                        if last_assistant_pos != -1:
                            # 截取最后一个assistant标记后的内容（包含标记本身）
                            output = generated_text[last_assistant_pos + len(assistant_marker):].lstrip()
                            if output:
                                yield output
                            generated_text = assistant_marker  # 保留标记作为锚点
                finally:
                    generate_thread.join()  # 确保即使发生异常也等待线程退出
            else:
                outputs = self.model.generate(**inputs, **params)
                yield self.tokenizer.decode(
                    outputs[0][inputs.input_ids.shape[-1]:],
                    skip_special_tokens=True
                )

        except Exception as e:
            logger.error(f"生成失败: {str(e)}")
            yield "生成失败，请检查模型配置"
    def _build_input_text(self, messages: List[Dict]) -> str:
        """使用tokenizer的对话模板构建输入文本"""
        input_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        return input_text