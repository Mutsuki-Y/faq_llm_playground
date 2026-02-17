"""Factory function for creating LLM clients based on configuration."""

from config import AppConfig
from llm.base import LLMClientBase


def create_llm_client(config: AppConfig) -> LLMClientBase:
    """設定に基づいてLLMクライアントを生成する。

    Args:
        config: アプリケーション設定

    Returns:
        設定されたプロバイダーのLLMクライアントインスタンス

    Raises:
        ValueError: サポートされていないプロバイダーが指定された場合
    """
    provider = config.llm_provider.lower()

    if provider == "openai":
        from llm.openai_client import OpenAIClient
        return OpenAIClient(config)
    elif provider == "vertexai":
        from llm.vertexai_client import VertexAIClient
        return VertexAIClient(config)
    else:
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Supported providers: 'openai', 'vertexai'"
        )
