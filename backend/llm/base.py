"""Abstract base class for LLM clients."""

from abc import ABC, abstractmethod
from pathlib import Path

from models import LLMResponse


class LLMClientBase(ABC):
    """LLMクライアントの抽象基底クラス。

    OpenAIとVertex AIを切り替え可能にするための共通インターフェースを定義する。
    """

    @abstractmethod
    async def chat_completion(self, messages: list[dict]) -> LLMResponse:
        """チャット補完を実行する。

        Args:
            messages: OpenAI互換のメッセージリスト（role/contentの辞書）

        Returns:
            プロバイダー非依存のLLMResponse
        """
        ...

    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]:
        """単一テキストのembeddingを生成する。

        Args:
            text: embedding対象のテキスト

        Returns:
            embeddingベクトル（floatのリスト）
        """
        ...

    @abstractmethod
    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """複数テキストのembeddingを一括生成する。

        Args:
            texts: embedding対象のテキストリスト

        Returns:
            embeddingベクトルのリスト
        """
        ...

    @abstractmethod
    async def describe_image(self, image_path: Path) -> str:
        """画像の説明テキストを生成する。

        Args:
            image_path: 画像ファイルのパス

        Returns:
            画像の説明テキスト
        """
        ...
