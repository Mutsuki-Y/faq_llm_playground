"""Property-based tests for ImageDocument metadata completeness.

**Feature: faq-chatbot, Property 8: ImageDocumentメタデータの完全性**
"""

from hypothesis import given, settings
from hypothesis import strategies as st
from models import ContentType, ImageDocument, ImageMetadata

# --- Strategies ---

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


# --- Property 8: ImageDocument metadata completeness ---
# **Feature: faq-chatbot, Property 8: ImageDocumentメタデータの完全性**
# **Validates: Requirements 3.4**


@given(doc=image_document_st)
@settings(max_examples=100)
def test_image_document_metadata_completeness(doc: ImageDocument):
    """For any ImageDocument created from an image file, the metadata
    contains image_path, a non-empty description, and source_file."""
    assert doc.metadata.image_path is not None
    assert len(doc.metadata.image_path) > 0
    assert doc.description is not None
    assert len(doc.description) > 0
    assert doc.metadata.source_file is not None
    assert len(doc.metadata.source_file) > 0
    assert doc.metadata.content_type == ContentType.IMAGE
