import json
import requests
from typing import AsyncGenerator
from adapters.model.base_model_adapter import BaseModelAdapter
from utils.logger import get_logger
import aiohttp

logger = get_logger(__name__)

class OllamaAdapter(BaseModelAdapter):
    def __init__(self, config: dict, event_bus):
        super().__init__(config, event_bus)
        """
        Ollama API适配器
        :param config: 配置加载器实例
        """
        self.endpoint = self._get_endpoint()
        self.model_name = self._get_model_name()
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _get_endpoint(self) -> str:
        """从配置获取API端点"""
        endpoint = self.config["endpoint"]
        if not endpoint.startswith(("https://", "https://")):
            endpoint = f"https://{endpoint}"
        return endpoint.rstrip("/")

    async def chat(
            self,
            messages: list[dict],
            stream: bool = False,
            **kwargs
    ) -> AsyncGenerator[str, None]:
        url = f"{self.endpoint}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
            **self._get_model_params(),
            **kwargs
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=payload) as response:
                    response.raise_for_status()

                    if stream:
                        async for line in response.content:
                            if line:
                                decoded = json.loads(line.decode("utf-8"))
                                if 'message' in decoded and 'content' in decoded['message']:
                                    yield decoded["message"]["content"]
                                else:
                                    yield "生成失败，请检查模型配置"
                    else:
                        result = await response.json()
                        if 'message' in result and 'content' in result['message']:
                            yield result["message"]["content"]
                        else:
                            yield "生成失败，请检查模型配置"
        except aiohttp.ClientError as e:
            logger.error(f"Ollama API请求失败: {str(e)}")
            yield f"请求失败: {str(e)}"
        except json.JSONDecodeError:
            logger.error("Ollama响应解析失败")
            yield "响应解析失败"

    def _get_model_params(self) -> dict:
        """从配置获取模型参数"""
        return {
            "options": {
                "temperature": self.config["temperature"],
                "top_p": self.config["top_p"],
                "max_tokens": self.config['max_tokens']
            }
        }