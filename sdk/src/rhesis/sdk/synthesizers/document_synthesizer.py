"""Simple document synthesizer for extracting text and creating chunks."""

from typing import Any, List, Optional

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.services.context_generator import ContextGenerator
from rhesis.sdk.services.extractor import DocumentExtractor
from rhesis.sdk.synthesizers.base import TestSetSynthesizer
from rhesis.sdk.synthesizers.prompt_synthesizer import PromptSynthesizer


class DocumentSynthesizer(TestSetSynthesizer):
    """Simple synthesizer that extracts text from documents and creates chunks."""

    def __init__(
        self,
        prompt_synthesizer: PromptSynthesizer,
        context_generator: Optional[ContextGenerator] = None,
        max_chunk_length: int = 1000,  # characters
        separator: str = "\n\n",
    ):
        """
        Initialize the document synthesizer.

        Args:
            prompt_synthesizer: PromptSynthesizer instance
                to use for generating synthetic data
            context_generator: ContextGenerator instance
                for creating context (creates default if None)
            max_chunk_length: Maximum characters per chunk
            separator: String to use when joining chunks
        """
        super().__init__()
        self.prompt_synthesizer = prompt_synthesizer
        self.context_generator = context_generator or ContextGenerator(
            max_chunk_length=max_chunk_length, separator=separator
        )
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
                - num_chunks: Number of chunks to select for context
                - Any other arguments to pass to PromptSynthesizer.generate()

        Returns:
            TestSet: Generated synthetic data from the complete pipeline
        """
        documents = kwargs.get("documents", [])
        max_chunk_length = kwargs.get("max_chunk_length", self.max_chunk_length)
        num_chunks = kwargs.get("num_chunks", None)

        # Process documents into chunks
        chunks = self.create_chunks_from_text(self.extract_text_from_documents(documents))

        # Generate context using ContextGenerator
        context = self.context_generator.generate_context_from_chunks(
            chunks, num_chunks, self.separator
        )

        # Get context metadata
        context_metadata = self.context_generator.get_context_metadata(
            chunks,
            self.context_generator.select_chunks(chunks, num_chunks),
            {
                "total_chunks": len(chunks),
                "max_chunk_length": max_chunk_length,
                "documents_processed": len(documents),
                "total_text_length": sum(len(chunk) for chunk in chunks),
            },
        )

        # Update the prompt synthesizer's context
        self.prompt_synthesizer.context = context

        # Generate using the updated prompt synthesizer
        result = self.prompt_synthesizer.generate(**kwargs)

        # Add document processing metadata with namespacing
        result.metadata = result.metadata or {}
        result.metadata["document_synthesizer"] = {
            "chunks_created": len(chunks),
            "context_metadata": context_metadata,
        }

        return result
