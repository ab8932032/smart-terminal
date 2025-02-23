import json
import logging
import requests
from typing import Optional, AsyncGenerator
from utils.logger import get_logger
from utils.config_loader import ModelConfig

logger = get_logger(__name__)

class OllamaAdapter:
    def __init__(self, config: ModelConfig):
        """
        Ollama API适配器
        :param config: 配置加载器实例
        """
        self.config = config
        self.endpoint = self._get_endpoint()
        self.model_name = self._get_model_name()
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _get_endpoint(self) -> str:
        """从配置获取API端点"""
        endpoint = self.config.get("model_providers.ollama.endpoint")
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"http://{endpoint}"
        return endpoint.rstrip("/")

    def _get_model_name(self) -> str:
        """从配置获取默认模型名称"""
        return self.config.get("model_providers.ollama.models.default")

    async def chat(
            self,
            messages: list[dict],
            stream: bool = False,
            **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        执行聊天请求
        :param messages: 消息历史 [{"role": "user", "content": "..."}]
        :param stream: 是否启用流式传输
        :return: 生成响应内容
        """
        url = f"{self.endpoint}/api/chat"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
            **self._get_model_params(),
            **kwargs
        }

        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                stream=stream,
                timeout=30
            )
            response.raise_for_status()

            if stream:
                for chunk in response.iter_lines():
                    if chunk:
                        decoded = json.loads(chunk.decode("utf-8"))
                        yield decoded["message"]["content"]
            else:
                result = response.json()
                yield result["message"]["content"]

        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API请求失败: {str(e)}")
            yield f"请求失败: {str(e)}"
        except json.JSONDecodeError:
            logger.error("Ollama响应解析失败")
            yield "响应解析失败"

    def list_models(self) -> list:
        """获取可用模型列表"""
        try:
            response = requests.get(
                f"{self.endpoint}/api/tags",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return [model["name"] for model in response.json()["models"]]
        except Exception as e:
            logger.error(f"获取模型列表失败: {str(e)}")
            return []

    def _get_model_params(self) -> dict:
        """从配置获取模型参数"""
        return {
            "options": {
                "temperature": self.config.get("model_providers.ollama.temperature", 0.7),
                "top_p": self.config.get("model_providers.ollama.top_p", 0.9),
                "max_tokens": self.config.get("model_providers.ollama.max_tokens", 2048)
            }
        }

    async def generate_embeddings(self, text: str) -> Optional[list[float]]:
        """生成文本嵌入"""
        try:
            response = requests.post(
                f"{self.endpoint}/api/embeddings",
                headers=self.headers,
                json={
                    "model": self.model_name,
                    "prompt": text
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            logger.error(f"生成嵌入失败: {str(e)}")
            return None

    async def check_health(self) -> bool:
        """检查服务健康状态"""
        try:
            response = requests.get(
                f"{self.endpoint}/",
                headers=self.headers,
                timeout=5
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
