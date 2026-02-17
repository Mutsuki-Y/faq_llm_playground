"""Property-based tests for vector store search results ordering and completeness.

**Feature: faq-chatbot, Property 3: ベクトルストア検索結果の順序と完全性**

Embedding生成はChromaDBのデフォルト（ローカルsentence-transformers）を使用。
"""

import asyncio
import shutil
import tempfile

import pytest
from config import AppConfig
from hypothesis import given, settings
from hypothesis import strategies as st
from models import (Chunk, ChunkMetadata, ContentType, ImageDocument,
                    ImageMetadata)
from store.vector_store import VectorStore


def _run_async(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

# --- Strategies ---

chunk_metadata_st = st.builds(
    ChunkMetadata,
    source_file=st.text(min_size=1, max_size=30, alphabet=st.characters(categories=("L", "N"))),
    sheet_name=st.text(min_size=1, max_size=30, alphabet=st.characters(categories=("L", "N"))),
    row_number=st.integers(min_value=1, max_value=100000),
    parent_category=st.text(min_size=1, max_size=30, alphabet=st.characters(categories=("L", "N"))),
    child_category=st.text(min_size=1, max_size=30, alphabet=st.characters(categories=("L", "N"))),
    title=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N"))),
    content_type=st.just(ContentType.TEXT),
)

image_metadata_st = st.builds(
    ImageMetadata,
    image_path=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N"))),
    source_file=st.text(min_size=1, max_size=30, alphabet=st.characters(categories=("L", "N"))),
    content_type=st.just(ContentType.IMAGE),
)


@st.composite
def chunks_st(draw):
    """Generate a list of unique chunks."""
    n = draw(st.integers(min_value=1, max_value=5))
    chunks = []
    for i in range(n):
        meta = draw(chunk_metadata_st)
        chunk = Chunk(
            chunk_id=f"chunk_{i}",
            text=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(categories=("L", "N")))),
            metadata=meta,
        )
        chunks.append(chunk)
    return chunks


@st.composite
def image_docs_st(draw):
    """Generate a list of unique image documents."""
    n = draw(st.integers(min_value=1, max_value=5))
    docs = []
    for i in range(n):
        meta = draw(image_metadata_st)
        doc = ImageDocument(
            doc_id=f"img_{i}",
            description=draw(st.text(min_size=1, max_size=100, alphabet=st.characters(categories=("L", "N")))),
            metadata=meta,
        )
        docs.append(doc)
    return docs


def _make_vector_store(tmp_dir: str) -> VectorStore:
    """Create a VectorStore with a temporary directory."""
    config = AppConfig(
        openai_api_key="test-key",
        chroma_persist_dir=tmp_dir,
    )
    return VectorStore(config)


# --- Property 3: Vector store search result ordering and completeness ---
# **Feature: faq-chatbot, Property 3: ベクトルストア検索結果の順序と完全性**
# **Validates: Requirements 4.2, 4.3, 3.5**


@given(
    chunks=chunks_st(),
    query_text=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N"))),
    top_k=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=50, deadline=None)
def test_vector_store_search_ordering_and_completeness(chunks, query_text, top_k):
    """For any set of stored documents and any query text, search results:
    (a) return at most k items,
    (b) are sorted by similarity score in descending order,
    (c) each result contains content, score, metadata, and content_type fields.
    """
    tmp_dir = tempfile.mkdtemp()
    try:
        store = _make_vector_store(tmp_dir)
        _run_async(store.add_chunks(chunks))
        results = _run_async(store.search(query_text, top_k=top_k))

        # (a) at most k results
        assert len(results) <= top_k
        assert len(results) <= len(chunks)

        # (b) descending score order
        scores = [r.score for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Scores not in descending order: {scores}"
            )

        # (c) each result has required fields
        for r in results:
            assert r.content is not None and isinstance(r.content, str)
            assert isinstance(r.score, float)
            assert isinstance(r.metadata, dict)
            assert r.content_type in (ContentType.TEXT, ContentType.IMAGE)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@given(
    img_docs=image_docs_st(),
    query_text=st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N"))),
    top_k=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=50, deadline=None)
def test_vector_store_image_results_contain_image_metadata(img_docs, query_text, top_k):
    """For image-type results, metadata includes image_path and description."""
    tmp_dir = tempfile.mkdtemp()
    try:
        store = _make_vector_store(tmp_dir)
        _run_async(store.add_image_documents(img_docs))
        results = _run_async(store.search(query_text, top_k=top_k))

        for r in results:
            assert r.content_type == ContentType.IMAGE
            assert "image_path" in r.metadata
            assert "description" in r.metadata
            assert r.metadata["image_path"] != ""
            assert r.metadata["description"] != ""
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
