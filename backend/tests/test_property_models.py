"""Property-based tests for data model serialization round-trips.

**Feature: faq-chatbot, Property 2: ChunkとImageDocumentのシリアライゼーション往復**
**Feature: faq-chatbot, Property 9: 評価テストケースJSON解析の往復**
"""

import json

from hypothesis import given, settings
from hypothesis import strategies as st
from models import (Chunk, ChunkMetadata, ContentType, EvalTestCase,
                    ImageDocument, ImageMetadata)

# --- Strategies ---

chunk_metadata_st = st.builds(
    ChunkMetadata,
    source_file=st.text(min_size=1, max_size=50),
    sheet_name=st.text(min_size=1, max_size=50),
    row_number=st.integers(min_value=1, max_value=100000),
    parent_category=st.text(min_size=1, max_size=50),
    child_category=st.text(min_size=1, max_size=50),
    title=st.text(min_size=1, max_size=200),
    content_type=st.just(ContentType.TEXT),
)

chunk_st = st.builds(
    Chunk,
    chunk_id=st.text(min_size=1, max_size=50),
    text=st.text(min_size=1, max_size=500),
    metadata=chunk_metadata_st,
)

image_metadata_st = st.builds(
    ImageMetadata,
    image_path=st.text(min_size=1, max_size=200),
    source_file=st.text(min_size=1, max_size=50),
    content_type=st.just(ContentType.IMAGE),
)

image_document_st = st.builds(
    ImageDocument,
    doc_id=st.text(min_size=1, max_size=50),
    description=st.text(min_size=1, max_size=500),
    metadata=image_metadata_st,
)


eval_test_case_st = st.builds(
    EvalTestCase,
    question=st.text(min_size=1, max_size=200),
    expected_answer=st.text(min_size=1, max_size=500),
    context=st.lists(st.text(min_size=1, max_size=200), min_size=0, max_size=5),
)


# --- Property 2: Chunk and ImageDocument serialization round-trip ---
# **Feature: faq-chatbot, Property 2: ChunkとImageDocumentのシリアライゼーション往復**
# **Validates: Requirements 9.3**


@given(chunk=chunk_st)
@settings(max_examples=100)
def test_chunk_serialization_round_trip(chunk: Chunk):
    """For any valid Chunk, serializing to JSON and deserializing back
    produces an identical object."""
    json_str = chunk.model_dump_json()
    restored = Chunk.model_validate_json(json_str)
    assert restored == chunk


@given(doc=image_document_st)
@settings(max_examples=100)
def test_image_document_serialization_round_trip(doc: ImageDocument):
    """For any valid ImageDocument, serializing to JSON and deserializing back
    produces an identical object."""
    json_str = doc.model_dump_json()
    restored = ImageDocument.model_validate_json(json_str)
    assert restored == doc


# Also test via dict intermediate (json.dumps/loads path)
@given(chunk=chunk_st)
@settings(max_examples=100)
def test_chunk_dict_round_trip(chunk: Chunk):
    """For any valid Chunk, converting to dict then JSON string and back
    produces an identical object."""
    data = json.loads(json.dumps(chunk.model_dump()))
    restored = Chunk.model_validate(data)
    assert restored == chunk


@given(doc=image_document_st)
@settings(max_examples=100)
def test_image_document_dict_round_trip(doc: ImageDocument):
    """For any valid ImageDocument, converting to dict then JSON string and back
    produces an identical object."""
    data = json.loads(json.dumps(doc.model_dump()))
    restored = ImageDocument.model_validate(data)
    assert restored == doc


# --- Property 9: EvalTestCase JSON round-trip ---
# **Feature: faq-chatbot, Property 9: 評価テストケースJSON解析の往復**
# **Validates: Requirements 13.2**


@given(tc=eval_test_case_st)
@settings(max_examples=100)
def test_eval_test_case_serialization_round_trip(tc: EvalTestCase):
    """For any valid EvalTestCase, serializing to JSON and deserializing back
    produces an identical object."""
    json_str = tc.model_dump_json()
    restored = EvalTestCase.model_validate_json(json_str)
    assert restored == tc


@given(tc=eval_test_case_st)
@settings(max_examples=100)
def test_eval_test_case_dict_round_trip(tc: EvalTestCase):
    """For any valid EvalTestCase, converting to dict then JSON string and back
    produces an identical object."""
    data = json.loads(json.dumps(tc.model_dump()))
    restored = EvalTestCase.model_validate(data)
    assert restored == tc
