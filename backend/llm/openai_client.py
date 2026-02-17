"""OpenAI API implementation of the LLM client."""

import base64
import mimetypes
from pathlib import Path

from config import AppConfig
from llm.base import LLMClientBase
from models import LLMResponse
from openai import AsyncOpenAI


class OpenAIClient(LLMClientBase):
    """OpenAI APIを使用したLLMクライアント実装。"""

    def __init__(self, config: AppConfig) -> None:
        self._client = AsyncOpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
        )
        self._model = config.openai_model

    async def chat_completion(self, messages: list[dict]) -> LLMResponse:
        """OpenAI Chat Completions APIでチャット補完を実行する。"""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            } if response.usage else {},
        )

    async def generate_embedding(self, text: str) -> list[float]:
        """OpenAI Embeddings APIで単一テキストのembeddingを生成する。"""
        response = await self._client.embeddings.create(
            model=self._embedding_model,
            input=text,
        )
        return response.data[0].embedding

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """OpenAI Embeddings APIで複数テキストのembeddingを一括生成する。"""
        response = await self._client.embeddings.create(
            model=self._embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def describe_image(self, image_path: Path) -> str:
        """OpenAIマルチモーダルAPIで画像の説明テキストを生成する。"""
        mime_type, _ = mimetypes.guess_type(str(image_path))
        if mime_type is None:
            mime_type = "image/png"

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        data_url = f"data:{mime_type};base64,{image_data}"

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "この画像の内容を詳しく説明してください。",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ],
                }
            ],
        )
        return response.choices[0].message.content or ""
