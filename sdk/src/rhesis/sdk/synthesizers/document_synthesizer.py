"""Simple document synthesizer for extracting text and creating chunks."""

from typing import Any, List

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.services.extractor import DocumentExtractor
from rhesis.sdk.synthesizers.base import TestSetSynthesizer
from rhesis.sdk.synthesizers.context_synthesizer import ContextSynthesizer


class DocumentSynthesizer(TestSetSynthesizer):
    """Simple synthesizer that extracts text from documents and creates chunks."""

    def __init__(
        self,
        context_synthesizer: ContextSynthesizer,
        max_chunk_length: int = 1000,  # characters
        separator: str = "\n\n",
    ):
        """
        Initialize the document synthesizer.

        Args:
            context_synthesizer: ContextSynthesizer instance to use for generating synthetic data
            max_chunk_length: Maximum characters per chunk
            separator: String to use when joining chunks
        """
        super().__init__()
        self.context_synthesizer = context_synthesizer
        self.max_chunk_length = max_chunk_length
        self.separator = separator
        self.document_extractor = DocumentExtractor()

    def extract_text_from_documents(self, documents: List[dict]) -> str:
        """
        Extract text from documents using the existing DocumentExtractor.

        Args:
            documents: List of document dictionaries with the following keys:
                - 'name': Name of the document.
                - 'description': Required description.
                - 'path': File path to the document (used if 'content' is not provided).
                - 'content': Raw text content of the document. Overrides 'path' if both are given.

        Returns:
            Combined text from all documents
        """
        try:
            extracted_texts = self.document_extractor.extract(documents)
            # Join all extracted texts with separator
            return self.separator.join(extracted_texts.values())
        except Exception as e:
            print(f"Warning: Failed to extract some documents: {e}")
            return ""

    def create_chunks_from_text(self, text: str) -> List[str]:
        """
        Create chunks from text based on length constraints.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        if not text:
            return []

        chunks = []
        start = 0

        while start < len(text):
            # Calculate end position for this chunk
            end = start + self.max_chunk_length

            # If this is not the last chunk, try to find a good break point
            if end < len(text):
                # Look for a good break point (newline, period, space)
                for i in range(end, max(start, end - 200), -1):
                    if text[i] in ["\n", ".", " "]:
                        end = i + 1
                        break

            # Extract the chunk
            chunk = text[start:end].strip()
            if chunk:  # Only add non-empty chunks
                chunks.append(chunk)

            # Move to next chunk
            start = end
            if start >= len(text):
                break

        return chunks

    def generate(self, **kwargs: Any) -> "TestSet":
        """
        Generate synthetic data using the complete pipeline.

        Args:
            **kwargs: Keyword arguments including:
                - documents: List of document dictionaries
                - max_chunk_length: Override default chunk length
                - Any other arguments to pass to ContextSynthesizer.generate()

        Returns:
            TestSet: Generated synthetic data from the complete pipeline
        """
        documents = kwargs.get("documents", [])
        max_chunk_length = kwargs.get("max_chunk_length", self.max_chunk_length)

        # Process documents into chunks
        chunks = self.process_documents(documents)

        # Add chunk metadata to kwargs
        kwargs.update(
            {
                "chunks": chunks,
                "chunk_metadata": {
                    "total_chunks": len(chunks),
                    "max_chunk_length": max_chunk_length,
                    "documents_processed": len(documents),
                    "total_text_length": sum(len(chunk) for chunk in chunks),
                },
            }
        )

        # Call ContextSynthesizer to generate the final result
        result = self.context_synthesizer.generate(**kwargs)

        # Add document processing metadata with namespacing
        result.metadata = result.metadata or {}
        result.metadata["document_synthesizer"] = {
            "chunks_created": len(chunks),
            "chunk_info": kwargs["chunk_metadata"],
        }

        return result
