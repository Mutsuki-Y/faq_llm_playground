"""MongoDB ベースのセッション管理モジュール。

motor（非同期MongoDBドライバー）を使用してチャット履歴をセッション単位で管理する。

MongoDBドキュメント構造:
    {
        "session_id": "uuid-v4",
        "messages": [
            {
                "question": "...",
                "answer": "...",
                "sources": [...],
                "timestamp": "2025-01-01T00:00:00+00:00"
            }
        ],
        "created_at": "2025-01-01T00:00:00+00:00"
    }

カスタマイズ:
    - config.mongodb_uri / config.mongodb_db_name で接続先を変更
    - config.history_limit でプロンプトに含める履歴件数を調整（ChatService経由）
"""

import uuid
from datetime import datetime, timezone

from config import AppConfig
from models import ChatMessage, SourceInfo
from motor.motor_asyncio import AsyncIOMotorClient


class SessionManager:
    """MongoDBを使用したチャット履歴のセッション管理。

    セッション作成、メッセージ追加、直近N件の履歴取得を提供する。
    """

    def __init__(self, config: AppConfig) -> None:
        self._client = AsyncIOMotorClient(config.mongodb_uri)
        self._db = self._client[config.mongodb_db_name]
        self._sessions = self._db["sessions"]

    async def create_session(self) -> str:
        """新しいセッションIDを発行し、MongoDBにセッションドキュメントを作成する。

        Returns:
            一意のセッションID
        """
        session_id = str(uuid.uuid4())
        await self._sessions.insert_one(
            {
                "session_id": session_id,
                "messages": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return session_id

    async def add_message(
        self,
        session_id: str,
        question: str,
        answer: str,
        sources: list[SourceInfo],
    ) -> None:
        """質問と回答をセッションのメッセージ配列に追加する。"""
        message = ChatMessage(
            question=question,
            answer=answer,
            sources=sources,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await self._sessions.update_one(
            {"session_id": session_id},
            {"$push": {"messages": message.model_dump()}},
        )

    async def get_recent_history(
        self, session_id: str, n: int = 5
    ) -> list[ChatMessage]:
        """直近N件の履歴を取得する。

        Args:
            session_id: セッションID
            n: 取得する履歴の最大件数

        Returns:
            直近N件のChatMessageリスト（古い順）
        """
        doc = await self._sessions.find_one({"session_id": session_id})
        if doc is None:
            return []

        messages_data = doc.get("messages", [])
        # 直近N件を取得（古い順で返す）
        recent = messages_data[-n:] if len(messages_data) > n else messages_data
        return [ChatMessage.model_validate(m) for m in recent]

    async def get_all_sessions(self) -> list[dict]:
        """全セッションの一覧を取得する（新しい順）。

        Returns:
            セッション情報のリスト（session_id, created_at, message_count, last_message）
        """
        cursor = self._sessions.find().sort("created_at", -1)
        sessions = []
        async for doc in cursor:
            messages = doc.get("messages", [])
            last_message = messages[-1]["question"] if messages else "新しいチャット"
            sessions.append({
                "session_id": doc["session_id"],
                "created_at": doc["created_at"],
                "message_count": len(messages),
                "last_message": last_message[:50] + ("..." if len(last_message) > 50 else ""),
            })
        return sessions

    async def get_full_history(self, session_id: str) -> list[ChatMessage]:
        """セッションの全履歴を取得する。

        Args:
            session_id: セッションID

        Returns:
            全ChatMessageリスト（古い順）
        """
        doc = await self._sessions.find_one({"session_id": session_id})
        if doc is None:
            return []

        messages_data = doc.get("messages", [])
        return [ChatMessage.model_validate(m) for m in messages_data]

    async def delete_session(self, session_id: str) -> bool:
        """セッションを削除する。

        Args:
            session_id: セッションID

        Returns:
            削除成功時True、セッションが存在しない場合False
        """
        result = await self._sessions.delete_one({"session_id": session_id})
        return result.deleted_count > 0
