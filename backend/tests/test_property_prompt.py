"""Property-based tests for prompt construction completeness.

**Feature: faq-chatbot, Property 4: プロンプト構築の完全性**
"""

from hypothesis import given, settings
from hypothesis import strategies as st
from models import ChatMessage, ContentType, SearchResult, SourceInfo
from services.chat_service import SYSTEM_PROMPT, ChatService

# --- Strategies ---

search_result_st = st.builds(
    SearchResult,
    content=st.text(min_size=1, max_size=200, alphabet=st.characters(categories=("L", "N"))),
    score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    metadata=st.fixed_dictionaries(
        {"source_file": st.text(min_size=1, max_size=30, alphabet=st.characters(categories=("L", "N")))}
    ),
    content_type=st.sampled_from([ContentType.TEXT, ContentType.IMAGE]),
)

source_info_st = st.builds(
    SourceInfo,
    content=st.text(min_size=1, max_size=100, alphabet=st.characters(categories=("L", "N"))),
    source_file=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N"))),
    content_type=st.just(ContentType.TEXT),
    score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    image_path=st.none(),
)

chat_message_st = st.builds(
    ChatMessage,
    question=st.text(min_size=1, max_size=100, alphabet=st.characters(categories=("L", "N"))),
    answer=st.text(min_size=1, max_size=200, alphabet=st.characters(categories=("L", "N"))),
    sources=st.lists(source_info_st, min_size=0, max_size=2),
    timestamp=st.text(min_size=1, max_size=30, alphabet=st.characters(categories=("L", "N"))),
)


# --- Property 4: Prompt construction completeness ---
# **Feature: faq-chatbot, Property 4: プロンプト構築の完全性**
# **Validates: Requirements 5.1, 5.4, 6.2**


@given(
    question=st.text(min_size=1, max_size=200, alphabet=st.characters(categories=("L", "N"))),
    context=st.lists(search_result_st, min_size=0, max_size=5),
    history=st.lists(chat_message_st, min_size=0, max_size=10),
    history_limit=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=100)
def test_prompt_construction_completeness(question, context, history, history_limit):
    """For any question, search results, and chat history, the constructed prompt:
    (a) contains a system prompt instructing FAQ-context-only answers,
    (b) includes all search result content in context,
    (c) includes the most recent min(N, len(history)) chat history messages,
    (d) includes the user's question.
    """
    # Trim history to simulate the history_limit config
    trimmed_history = history[-history_limit:] if len(history) > history_limit else history

    # Call _build_prompt directly (it's a pure function on the instance)
    messages = ChatService._build_prompt(None, question, context, trimmed_history)

    # (a) System prompt is present and instructs FAQ-context-only answers
    system_messages = [m for m in messages if m["role"] == "system"]
    assert len(system_messages) >= 1
    assert system_messages[0]["content"] == SYSTEM_PROMPT

    # (b) All search result content appears in the context system message
    if context:
        context_msg = system_messages[1]["content"]
        for result in context:
            assert result.content in context_msg, (
                f"Search result content '{result.content}' not found in context message"
            )

    # (c) Chat history messages are included
    user_msgs = [m for m in messages if m["role"] == "user"]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]

    expected_history_count = len(trimmed_history)
    # History user messages + the final question = expected_history_count + 1
    assert len(user_msgs) == expected_history_count + 1
    assert len(assistant_msgs) == expected_history_count

    for i, hist_msg in enumerate(trimmed_history):
        assert user_msgs[i]["content"] == hist_msg.question
        assert assistant_msgs[i]["content"] == hist_msg.answer

    # (d) The last user message is the question
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == question
