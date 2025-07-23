from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Template

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.synthesizers.base import TestSetSynthesizer
from rhesis.sdk.services.extractor import DocumentExtractor
from rhesis.sdk.utils import extract_json_from_text, clean_and_validate_tests


class PromptSynthesizer(TestSetSynthesizer):
    """A synthesizer that generates test cases based on a prompt using LLM."""

    def __init__(self, prompt: str, batch_size: int = 20, system_prompt: Optional[str] = None, documents: Optional[List[Dict]] = None):
        """
        Initialize the PromptSynthesizer.

        Args:
            prompt: The generation prompt to use
            batch_size: Maximum number of tests to generate in a single LLM call (reduced default for stability)
            system_prompt: Optional custom system prompt template to override the default
            documents: Optional list of documents to extract content from. Each document should have:
                - name (str): Unique identifier or label for the document
                - description (str): Short description of the document's purpose or content
                - path (str): Local file path (optional, can be empty if content is provided)
                - content (str): Pre-provided document content (optional)
        """
        super().__init__(batch_size=batch_size)
        self.prompt = prompt
        self.documents = documents or []
        
        # Initialize document extractor for processing document files
        self.document_extractor = DocumentExtractor()
        
        # Extract content from documents if provided
        self.extracted_documents = {}
        if self.documents:
            try:
                self.extracted_documents = self.document_extractor.extract(self.documents)
            except Exception as e:
                print(f"Warning: Failed to extract some documents: {e}")

        if system_prompt:
            self.system_prompt = Template(system_prompt)
        else:
            # Load default system prompt from assets
            prompt_path = Path(__file__).parent / "assets" / "prompt_synthesizer.md"
            with open(prompt_path, "r") as f:
                self.system_prompt = Template(f.read())

    def _generate_batch(self, num_tests: int) -> List[Dict[str, Any]]:
        """Generate a batch of test cases with improved error handling."""
        # Prepare document context for the prompt
        document_context = ""
        if self.extracted_documents:
            document_context = "\n\n".join([
                f"Document '{name}':\n{content}"
                for name, content in self.extracted_documents.items()
            ])
        
        formatted_prompt = self.system_prompt.render(
            generation_prompt=self.prompt, 
            num_tests=num_tests,
            document_context=document_context
        )

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Use run() method with default parameters
                response = self.llm_service.run(prompt=formatted_prompt)
                
                # Debug logging to understand response structure
                print(f"DEBUG: Response type: {type(response)}")
                if isinstance(response, dict):
                    print(f"DEBUG: Dict keys: {list(response.keys())}")
                    print(f"DEBUG: Dict content preview: {str(response)[:300]}...")
                
                # Handle different response types
                test_cases = []
                
                if isinstance(response, dict):
                    # Try to extract tests from various possible dict structures
                    if "tests" in response:
                        test_cases = response["tests"]
                    else:
                        # Check if the dict contains test-like structures
                        # Look for common keys that might contain test arrays
                        for key in ["test_cases", "data", "results", "items"]:
                            if key in response and isinstance(response[key], list):
                                test_cases = response[key]
                                break
                        
                        # If still no tests found, check if the dict itself looks like a single test
                        if not test_cases and any(key in response for key in ["input", "output", "expected", "question", "answer"]):
                            test_cases = [response]
                            
                elif isinstance(response, str):
                    # Use utility function for robust JSON extraction
                    parsed_response = extract_json_from_text(response)
                    test_cases = parsed_response.get("tests", [])
                elif isinstance(response, list):
                    # Response is already a list of test cases
                    test_cases = response
                else:
                    raise ValueError(f"Unexpected response type: {type(response)}. Response content: {str(response)[:200]}...")

                # Clean and validate test cases using utility function
                valid_test_cases = clean_and_validate_tests(test_cases)

                if valid_test_cases:
                    # Add metadata to each test case
                    return [
                        {
                            **test,
                            "metadata": {
                                "generated_by": "PromptSynthesizer",
                                "attempt": attempt + 1,
                                "documents_used": list(self.extracted_documents.keys()) if self.extracted_documents else [],
                            },
                        }
                        for test in valid_test_cases[:num_tests]
                    ]

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_attempts - 1:
                    raise ValueError(f"Failed to generate test cases after {max_attempts} attempts: {e}")

        return []

    def generate(self, **kwargs: Any) -> TestSet:
        """
        Generate test cases based on the given prompt.

        Args:
            **kwargs: Keyword arguments, supports:
                num_tests (int): Total number of test cases to generate. Defaults to 5.

        Returns:
            TestSet: A TestSet entity containing the generated test cases
        """
        num_tests = kwargs.get("num_tests", 5)
        if not isinstance(num_tests, int):
            raise TypeError("num_tests must be an integer")

        all_test_cases = []

        # For large numbers, use chunking to avoid JSON parsing issues
        if num_tests > self.batch_size:
            # Generate in chunks
            remaining_tests = num_tests
            while remaining_tests > 0:
                chunk_size = min(self.batch_size, remaining_tests)
                try:
                    chunk_tests = self._generate_batch(chunk_size)
                    all_test_cases.extend(chunk_tests)
                    remaining_tests -= len(chunk_tests)
                    
                    # If we didn't get the expected number, try again with a smaller chunk
                    if len(chunk_tests) < chunk_size and chunk_size > 5:
                        remaining_tests += (chunk_size - len(chunk_tests))
                        self.batch_size = max(5, self.batch_size // 2)
                        
                except Exception as e:
                    print(f"Error generating chunk of {chunk_size} tests: {e}")
                    # Try with smaller batch size
                    if self.batch_size > 5:
                        self.batch_size = max(5, self.batch_size // 2)
                        continue
                    else:
                        break
        else:
            # Generate all tests in a single batch
            all_test_cases = self._generate_batch(num_tests)

        # Ensure we have some test cases
        if not all_test_cases:
            raise ValueError("Failed to generate any valid test cases")

        test_set = TestSet(
            tests=all_test_cases,
            metadata={
                "generation_prompt": self.prompt,
                "num_tests": len(all_test_cases),
                "requested_tests": num_tests,
                "batch_size": self.batch_size,
                "synthesizer": "PromptSynthesizer",
                "documents_used": list(self.extracted_documents.keys()) if self.extracted_documents else [],
            },
        )

        # Set properties based on the generated tests
        test_set.set_properties()

        return test_set
