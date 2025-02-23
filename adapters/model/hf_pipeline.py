# adapters/model/hf_pipeline.py
import torch
from transformers import pipeline, BitsAndBytesConfig

class HuggingFacePipeline:
    def __init__(self, model_config):
        self._init_quant_config(model_config)
        self.pipeline = self._load_pipeline(model_config)
        
    def _init_quant_config(self, config):
        """初始化量化配置"""
        self.quant_config = BitsAndBytesConfig(
            load_in_4bit=config['quantization']['enabled'],
            bnb_4bit_quant_type=config['quantization']['type'],
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True
        )

    def _load_pipeline(self, config):
        """加载生成管道"""
        if torch.cuda.is_available():
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.benchmark = True

        return pipeline(
            "text-generation",
            model=config['model_name'],
            device_map="auto",
            model_kwargs={
                "quantization_config": self.quant_config,
                "attn_implementation": config['model_args']['attn_implementation']
            }
        )