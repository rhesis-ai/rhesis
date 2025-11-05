"""Utility functions for common synthesizer operations."""

from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, Template

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.models.base import BaseLLM


def load_prompt_template(prompt_template_file: str) -> "Template":
    """Load prompt template from assets or use custom prompt."""
    templates_path = Path(__file__).parent / "assets"
    environment = Environment(loader=FileSystemLoader(templates_path))
    template = environment.get_template(prompt_template_file)
    return template


def create_test_set_metadata(synthesizer_name: str, batch_size: int, **kwargs) -> Dict[str, Any]:
    """Create standardized metadata for test sets."""
    base_metadata = {
        "synthesizer": synthesizer_name,
        "batch_size": batch_size,
    }
    base_metadata.update(kwargs)
    return base_metadata


def create_test_set(tests: List[Dict], model: BaseLLM, **metadata_kwargs) -> "TestSet":
    """Create and configure a TestSet with metadata."""
    from rhesis.sdk.entities.test_set import TestSet

    metadata = create_test_set_metadata(**metadata_kwargs)
    test_set = TestSet(tests=tests, metadata=metadata, model=model)
    test_set.set_properties()
    return test_set
