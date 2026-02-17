"""Vertex AI stub implementation of the LLM client (future use)."""

from pathlib import Path

from config import AppConfig
from llm.base import LLMClientBase
from models import LLMResponse


class VertexAIClient(LLMClientBase):
    """Vertex AI LLMクライアントのスタブ実装。

    将来のGCP/Vertex AI移行用。現時点ではすべてのメソッドが
    NotImplementedErrorを送出する。
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    async def chat_completion(self, messages: list[dict]) -> LLMResponse:
        raise NotImplementedError("Vertex AI client is not yet implemented")

    async def generate_embedding(self, text: str) -> list[float]:
        raise NotImplementedError("Vertex AI client is not yet implemented")

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Vertex AI client is not yet implemented")

    async def describe_image(self, image_path: Path) -> str:
        raise NotImplementedError("Vertex AI client is not yet implemented")
