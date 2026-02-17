"""RAG チャットサービスモジュール。

このモジュールはRAG（Retrieval-Augmented Generation）パイプラインの
オーケストレーションを担当する。

処理フロー:
    1. ユーザーの質問テキストをEmbeddingに変換
    2. ベクトルストアでコサイン類似度検索（上位k件の関連ドキュメントを取得）
    3. MongoDBから同一セッションの直近N件のチャット履歴を取得
    4. システムプロンプト + FAQコンテキスト + チャット履歴 + 質問でプロンプトを構築
    5. LLMで回答を生成
    6. 質問と回答をセッション履歴に保存して返却

カスタマイズ:
    - SYSTEM_PROMPT を編集すると回答のトーンや制約を変更できる
    - config.top_k で検索結果の件数を調整できる
    - config.history_limit でプロンプトに含める履歴件数を調整できる
"""

import logging

from config import AppConfig
from llm.base import LLMClientBase
from models import (ChatMessage, ChatResponse, ContentType, SearchResult,
                    SourceInfo)
from services.session_manager import SessionManager
from store.vector_store import VectorStore

logger = logging.getLogger(__name__)

# LLMに送信するシステムプロンプト。
# FAQコンテキストに基づいた回答のみを生成するよう指示する。
# 回答のトーンや制約を変更したい場合はここを編集する。
SYSTEM_PROMPT = (
    "あなたはFAQチャットボットです。"
    "提供されたFAQコンテキストに基づいてのみ回答してください。"
    "コンテキストに含まれない情報については「該当する情報が見つかりませんでした」と回答してください。"
    "回答は簡潔かつ正確に、日本語で行ってください。"
)


class ChatService:
    """RAGパイプラインのオーケストレーション。

    各コンポーネント（LLMクライアント、ベクトルストア、セッションマネージャー）を
    組み合わせて、質問に対する回答を生成する。

    Attributes:
        _llm: LLMクライアント（Embedding生成 + チャット補完）
        _store: ベクトルストア（ChromaDB、類似度検索）
        _session: セッションマネージャー（MongoDB、チャット履歴）
        _config: アプリケーション設定（top_k, history_limit等）
    """

    def __init__(
        self,
        llm_client: LLMClientBase,
        vector_store: VectorStore,
        session_manager: SessionManager,
        config: AppConfig,
    ) -> None:
        self._llm = llm_client
        self._store = vector_store
        self._session = session_manager
        self._config = config

    async def answer(self, question: str, session_id: str) -> ChatResponse:
        """質問に対してRAGパターンで回答を生成する。"""
        # ベクトルストアが空の場合
        if self._store.is_empty():
            return ChatResponse(
                answer="ナレッジベースが未構築です。先にデータの取り込みを実行してください。",
                sources=[],
                session_id=session_id,
            )

        try:
            # 1. テキストクエリで類似検索（Embeddingはローカル自動生成）
            search_results = await self._store.search(
                question, top_k=self._config.top_k
            )

            # 2. チャット履歴を取得
            history = await self._session.get_recent_history(
                session_id, n=self._config.history_limit
            )

            # 3. プロンプト構築
            messages = self._build_prompt(question, search_results, history)

            # 4. LLM回答生成
            llm_response = await self._llm.chat_completion(messages)

            # 5. ソース情報を構築
            sources = self._build_sources(search_results)

            # 6. 履歴に保存
            await self._session.add_message(
                session_id, question, llm_response.content, sources
            )

            return ChatResponse(
                answer=llm_response.content,
                sources=sources,
                session_id=session_id,
            )
        except Exception:
            logger.exception("回答生成に失敗しました")
            return ChatResponse(
                answer="回答の生成に失敗しました。しばらくしてから再度お試しください。",
                sources=[],
                session_id=session_id,
            )

    def _build_prompt(
        self,
        question: str,
        context: list[SearchResult],
        history: list[ChatMessage],
    ) -> list[dict]:
        """システムプロンプト、コンテキスト、履歴、質問を組み合わせたプロンプトを構築する。"""
        messages: list[dict] = []

        # (a) システムプロンプト
        messages.append({"role": "system", "content": SYSTEM_PROMPT})

        # (b) コンテキスト
        if context:
            context_parts = []
            for i, result in enumerate(context, 1):
                context_parts.append(f"[{i}] {result.content}")
            context_text = "\n\n".join(context_parts)
            messages.append(
                {
                    "role": "system",
                    "content": f"以下はFAQコンテキストです:\n\n{context_text}",
                }
            )

        # (c) チャット履歴
        for msg in history:
            messages.append({"role": "user", "content": msg.question})
            messages.append({"role": "assistant", "content": msg.answer})

        # (d) ユーザーの質問
        messages.append({"role": "user", "content": question})

        return messages

    @staticmethod
    def _build_sources(search_results: list[SearchResult]) -> list[SourceInfo]:
        """検索結果からSourceInfoリストを構築する。"""
        sources = []
        for r in search_results:
            source = SourceInfo(
                content=r.content,
                source_file=r.metadata.get("source_file", ""),
                content_type=r.content_type,
                score=r.score,
                image_path=r.metadata.get("image_path") if r.content_type == ContentType.IMAGE else None,
            )
            sources.append(source)
        return sources
