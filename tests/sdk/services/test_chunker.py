from rhesis.sdk.services.chunker import (
    ChunkingService,
    IdentityChunker,
    RecursiveChunker,
    SentenceChunker,
    TokenChunker,
)
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


def test_token_chunker():
    chunker = TokenChunker(chunk_size=10)
    text = "This is a very long text that should be chunked into smaller parts"

    chunks = chunker.chunk(text)

    assert len(chunks) == 2
    assert chunks[0] == "This is a very long text that should be chunk"
    assert chunks[1] == "ed into smaller parts"


def test_sentence_chunker():
    chunker = SentenceChunker(chunk_size=20)
    text = "This is a sentence. This is another sentence. And a third one."

    chunks = chunker.chunk(text)

    assert len(chunks) > 0
    assert "This is a sentence." in chunks[0]


def test_recursive_chunker():
    chunker = RecursiveChunker(chunk_size=10)
    text = "This is a very long text that should be chunked into smaller parts"

    chunks = chunker.chunk(text)

    assert len(chunks) == 2
    assert chunks[0] == "This is a very long text that should be chunk"
    assert chunks[1] == "ed into smaller parts"


def test_chunking_service(document_source):
    text_source = SourceSpecification(
        type=SourceType.TEXT,
        name="test",
        description="test",
        metadata={"content": "This is a very long text that should be chunked into smaller parts"},
    )
    extracted_sources = ExtractionService.extract([document_source, text_source])
    chunker = ChunkingService(
        sources=extracted_sources, strategy=RecursiveChunker(chunk_size=5)
    )

    chunks = chunker.chunk()

    assert len(chunks) == 4
    assert chunks[0].content == "Test Rhesis"
    assert chunks[1].content == "This is a very long"
    assert chunks[2].content == " text that should be chunk"
    assert chunks[3].content == "ed into smaller parts"
