from app.core.canonicalize import rag_context_to_blocks


def test_rag_context_accepts_content_and_metadata_shape():
    docs = [
        {
            "content": "Hello from RAG",
            "metadata": {"source": "doc_1", "type": "doc"},
        }
    ]

    blocks = rag_context_to_blocks(docs, model="gpt-4o-mini")
    assert len(blocks) == 1
    assert blocks[0].content == "Hello from RAG"
    assert blocks[0].type.value == "doc"


def test_rag_context_accepts_legacy_text_key():
    docs = [{"text": "Legacy text", "id": "abc", "source": "legacy"}]
    blocks = rag_context_to_blocks(docs, model="gpt-4o-mini")
    assert len(blocks) == 1
    assert blocks[0].content == "Legacy text"


def test_rag_context_skips_empty_docs():
    docs = [{"content": "  "}, {"metadata": {"source": "x"}}]
    blocks = rag_context_to_blocks(docs, model="gpt-4o-mini")
    assert blocks == []

