"""Property-based tests for API validation (422 responses).

**Feature: faq-chatbot, Property 7: 不正リクエストに対する422レスポンス**
"""

from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from main import app

client = TestClient(app, raise_server_exceptions=False)


# Strategy: generate request bodies that are missing required fields
# ChatRequest requires both "question" (str) and "session_id" (str)

# Bodies missing "question"
missing_question_st = st.fixed_dictionaries(
    {"session_id": st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N")))},
)

# Bodies missing "session_id"
missing_session_id_st = st.fixed_dictionaries(
    {"question": st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N")))},
)

# Bodies with wrong types
wrong_type_st = st.one_of(
    st.fixed_dictionaries({"question": st.integers(), "session_id": st.text(min_size=1, max_size=20)}),
    st.fixed_dictionaries({"question": st.text(min_size=1, max_size=20), "session_id": st.integers()}),
    st.fixed_dictionaries({"question": st.lists(st.integers(), max_size=3), "session_id": st.text(min_size=1, max_size=20)}),
)

# Empty body
empty_body_st = st.just({})

# Combine all invalid body strategies
invalid_body_st = st.one_of(
    missing_question_st,
    missing_session_id_st,
    wrong_type_st,
    empty_body_st,
)


# --- Property 7: Invalid requests return 422 ---
# **Feature: faq-chatbot, Property 7: 不正リクエストに対する422レスポンス**
# **Validates: Requirements 7.3**


@given(body=invalid_body_st)
@settings(max_examples=100)
def test_invalid_chat_request_returns_422(body):
    """For any invalid or incomplete request body sent to POST /api/chat
    (e.g., missing question or session_id), the API returns HTTP 422
    with a detailed error message."""
    response = client.post("/api/chat", json=body)
    assert response.status_code == 422, (
        f"Expected 422 for body {body}, got {response.status_code}"
    )
    error_detail = response.json()
    assert "detail" in error_detail, (
        f"Expected 'detail' key in error response, got {error_detail}"
    )
