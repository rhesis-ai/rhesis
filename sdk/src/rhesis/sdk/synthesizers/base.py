from abc import ABC, abstractmethod
from typing import Any, List

from tqdm.auto import tqdm

from rhesis.sdk.entities.test_set import TestSet


class TestSetSynthesizer(ABC):
    """Base class for all test set synthesizers."""

    def __init__(self, batch_size: int = 5):
        """
        Initialize the base synthesizer.

        Args:
            batch_size: Maximum number of items to process in a single LLM call
        """
        self.batch_size = batch_size

    def _process_with_progress(
        self,
        items: List[Any],
        process_func: Any,
        desc: str = "Processing",
    ) -> List[Any]:
        """Process items with a progress bar."""
        results = []
        with tqdm(total=len(items), desc=desc) as pbar:
            for item in items:
                result = process_func(item)
                if isinstance(result, list):
                    results.extend(result)
                else:
                    results.append(result)
                pbar.update(1)
        return results

    @abstractmethod
    def generate(self, **kwargs: Any) -> TestSet:
        """
        Generate a test set based on the synthesizer's implementation.

        Args:
            **kwargs: Additional keyword arguments for test set generation

        Returns:
            TestSet: A TestSet entity containing the generated test cases
        """
        pass
