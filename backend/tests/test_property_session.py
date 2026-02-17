"""Property-based tests for session management.

**Feature: faq-chatbot, Property 5: セッション履歴の永続化往復**
**Feature: faq-chatbot, Property 6: 新規セッション初期化**
"""

import asyncio
import uuid

from config import AppConfig
from hypothesis import given, settings
from hypothesis import strategies as st
from models import ContentType, SourceInfo
from motor.motor_asyncio import AsyncIOMotorClient
from services.session_manager import SessionManager

# --- Strategies ---

source_info_st = st.builds(
    SourceInfo,
    content=st.text(min_size=1, max_size=100, alphabet=st.characters(categories=("L", "N"))),
    source_file=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N"))),
    content_type=st.sampled_from([ContentType.TEXT, ContentType.IMAGE]),
    score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    image_path=st.one_of(
        st.none(),
        st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N"))),
    ),
)

message_pair_st = st.tuples(
    st.text(min_size=1, max_size=100, alphabet=st.characters(categories=("L", "N"))),
    st.text(min_size=1, max_size=200, alphabet=st.characters(categories=("L", "N"))),
    st.lists(source_info_st, min_size=0, max_size=3),
)


# --- Property 5: Session history persistence round-trip ---
# **Feature: faq-chatbot, Property 5: セッション履歴の永続化往復**
# **Validates: Requirements 6.1, 6.4**


@given(
    messages=st.lists(message_pair_st, min_size=1, max_size=5),
)
@settings(max_examples=100, deadline=None)
def test_session_history_round_trip(messages):
    """For any sequence of question/answer pairs in a session,
    saving to MongoDB and reading back produces identical ChatMessage objects."""
    db_name = f"test_{uuid.uuid4().hex[:8]}"

    async def _run():
        config = AppConfig(
            openai_api_key="test-key",
            mongodb_uri="mongodb://mongodb:27017",
            mongodb_db_name=db_name,
        )
        manager = SessionManager(config)
        try:
            session_id = await manager.create_session()

            for question, answer, sources in messages:
                await manager.add_message(session_id, question, answer, sources)

            history = await manager.get_recent_history(
                session_id, n=len(messages)
            )

            assert len(history) == len(messages)

            for (question, answer, sources), msg in zip(messages, history):
                assert msg.question == question
                assert msg.answer == answer
                assert len(msg.sources) == len(sources)
                for orig, restored in zip(sources, msg.sources):
                    assert orig.content == restored.content
                    assert orig.source_file == restored.source_file
                    assert orig.content_type == restored.content_type
                    assert orig.score == restored.score
                    assert orig.image_path == restored.image_path
                assert msg.timestamp != ""
        finally:
            client = AsyncIOMotorClient(config.mongodb_uri)
            await client.drop_database(db_name)
            client.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()


# --- Property 6: New session initialization ---
# **Feature: faq-chatbot, Property 6: 新規セッション初期化**
# **Validates: Requirements 6.5**


@given(
    n_sessions=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100, deadline=None)
def test_new_session_initialization(n_sessions):
    """For any number of sessions created, each has a unique ID
    and empty chat history."""
    db_name = f"test_{uuid.uuid4().hex[:8]}"

    async def _run():
        config = AppConfig(
            openai_api_key="test-key",
            mongodb_uri="mongodb://mongodb:27017",
            mongodb_db_name=db_name,
        )
        manager = SessionManager(config)
        try:
            session_ids = []
            for _ in range(n_sessions):
                sid = await manager.create_session()
                session_ids.append(sid)

            # All session IDs are unique
            assert len(set(session_ids)) == n_sessions

            # Each session has empty history
            for sid in session_ids:
                history = await manager.get_recent_history(sid)
                assert len(history) == 0
        finally:
            client = AsyncIOMotorClient(config.mongodb_uri)
            await client.drop_database(db_name)
            client.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()
