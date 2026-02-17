"""Property-based tests for ETL pipeline filtering and chunk generation.

**Feature: faq-chatbot, Property 1: FAQフィルタリングとチャンク生成の正しさ**
"""

from etl.excel_reader import ExcelReader
from hypothesis import given, settings
from hypothesis import strategies as st
from models import FAQEntry

# --- Strategies ---

# Status is either "公開" or some other value
status_st = st.sampled_from(["公開", "非公開", "下書き", "削除済み"])

faq_entry_st = st.builds(
    FAQEntry,
    no=st.integers(min_value=1, max_value=100000),
    status=status_st,
    parent_category=st.text(min_size=1, max_size=50),
    child_category=st.text(min_size=1, max_size=50),
    title=st.text(min_size=1, max_size=200),
    body=st.text(min_size=1, max_size=500),
    source_file=st.text(min_size=1, max_size=50),
    sheet_name=st.text(min_size=1, max_size=50),
    row_number=st.integers(min_value=2, max_value=100000),
)


# --- Property 1: FAQ filtering and chunk generation correctness ---
# **Feature: faq-chatbot, Property 1: FAQフィルタリングとチャンク生成の正しさ**
# **Validates: Requirements 1.2, 1.3, 1.5**


@given(entries=st.lists(faq_entry_st, min_size=0, max_size=20))
@settings(max_examples=100)
def test_filter_returns_only_published_entries(entries: list[FAQEntry]):
    """For any list of FAQEntry objects, filtering returns only entries
    with status '公開', and the count matches."""
    reader = ExcelReader()
    published = reader.filter_published(entries)
    expected_count = sum(1 for e in entries if e.status == "公開")

    assert len(published) == expected_count
    assert all(e.status == "公開" for e in published)


@given(entry=faq_entry_st.filter(lambda e: e.status == "公開"))
@settings(max_examples=100)
def test_chunk_text_is_title_plus_body(entry: FAQEntry):
    """For any published FAQEntry, the generated chunk text equals
    title + newline + body."""
    reader = ExcelReader()
    chunk = reader.faq_entry_to_chunk(entry)

    assert chunk.text == f"{entry.title}\n{entry.body}"


@given(entry=faq_entry_st.filter(lambda e: e.status == "公開"))
@settings(max_examples=100)
def test_chunk_metadata_matches_source_entry(entry: FAQEntry):
    """For any published FAQEntry, the generated chunk metadata matches
    the source entry fields."""
    reader = ExcelReader()
    chunk = reader.faq_entry_to_chunk(entry)

    assert chunk.metadata.source_file == entry.source_file
    assert chunk.metadata.sheet_name == entry.sheet_name
    assert chunk.metadata.row_number == entry.row_number
    assert chunk.metadata.parent_category == entry.parent_category
    assert chunk.metadata.child_category == entry.child_category
    assert chunk.metadata.title == entry.title


@given(entries=st.lists(faq_entry_st, min_size=0, max_size=20))
@settings(max_examples=100)
def test_chunk_count_equals_published_count(entries: list[FAQEntry]):
    """For any list of FAQEntry objects, the number of generated chunks
    equals the number of published entries."""
    reader = ExcelReader()
    published = reader.filter_published(entries)
    chunks = [reader.faq_entry_to_chunk(e) for e in published]

    assert len(chunks) == sum(1 for e in entries if e.status == "公開")
