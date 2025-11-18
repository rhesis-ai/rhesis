from rhesis.sdk.services.chunker import ChunkingService, IdentityChunker, SemanticChunker
from rhesis.sdk.services.extractor import (
    ExtractionService,
    SourceSpecification,
    SourceType,
)


def test_identity_chunker():
    chunker = IdentityChunker()
    text = "This is a test text"

    chunks = chunker.chunk(text)

    assert chunks == [text]


def test_semantic_chunker():
    chunker = SemanticChunker(max_tokens_per_chunk=10)
    text = "This is a very long text that should be chunked into smaller parts"

    chunks = chunker.chunk(text)

    assert chunks == ["This is a very long text that should be chunk", "ed into smaller parts"]


def test_chunking_service(document_source):
    text_source = SourceSpecification(
        type=SourceType.TEXT,
        name="test",
        description="test",
        metadata={"content": "This is a very long text that should be chunked into smaller parts"},
    )
    extracted_sources = ExtractionService.extract([document_source, text_source])
    chunker = ChunkingService(
        sources=extracted_sources, strategy=SemanticChunker(max_tokens_per_chunk=5)
    )

    chunks = chunker.chunk()

    assert len(chunks) == 4
    assert chunks[0].content == "Test Rhesis"
    assert chunks[1].content == "This is a very long"
    assert chunks[2].content == "text that should be chu"
