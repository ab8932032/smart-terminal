# adapters/model/hf_pipeline.py
import logging
from typing import List, Dict
from transformers import pipeline, AutoTokenizer, BitsAndBytesConfig
from utils.logger import get_logger

logger = get_logger(__name__)

class HuggingFacePipeline:
    def __init__(self, config: dict):
        """
        HuggingFace Pipeline适配器
        :param config: 包含以下键的配置字典：
            - model_name: 模型名称或路径
            - quantization: 量化配置
            - generation_params: 生成参数
        """
        self.config = config
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

    def generate(self, input_text: str, **kwargs) -> List[Dict]:
        """
        执行文本生成
        :param input_text: 输入文本
        :return: 生成结果列表 [{"generated_text": "..."}]
        """
        try:
            params = {**self.config['generation_params'], **kwargs}
            return self.pipeline(input_text, **params)
        except Exception as e:
            logger.error(f"生成失败: {str(e)}")
            return [{"generated_text": "生成失败，请检查模型配置"}]
