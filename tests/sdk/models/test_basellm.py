import pytest

from rhesis.sdk.models.base import BaseLLM


def test_base_llm_cannot_be_instantiated():
    """Test that BaseLLM cannot be instantiated directly due to abstract methods."""
    with pytest.raises(TypeError):
        BaseLLM("test-model")


def test_base_llm_abstract_methods():
    """Test that BaseLLM has the expected abstract methods."""
    assert hasattr(BaseLLM, "load_model")
    assert hasattr(BaseLLM, "generate")
    assert hasattr(BaseLLM, "get_model_name")

    # Check that abstract methods are actually abstract
    assert BaseLLM.load_model.__isabstractmethod__
    assert BaseLLM.generate.__isabstractmethod__


def test_base_llm_concrete_methods():
    """Test that concrete methods work correctly."""

    # Create a minimal concrete implementation for testing
    class TestLLM(BaseLLM):
        def load_model(self, *args, **kwargs):
            return "test-model-object"

        def generate(self, *args, **kwargs) -> str:
            return "test-response"

    model_name = "test-model"
    test_llm = TestLLM(model_name)

    # Test concrete method
    assert test_llm.get_model_name() == "Class name: TestLLM, model name: test-model"
    assert model_name in test_llm.model_name
    assert test_llm.model == "test-model-object"


def test_base_llm_generate_multimodal_not_implemented():
    """Test that generate_multimodal raises NotImplementedError on base class."""

    class TestLLM(BaseLLM):
        def load_model(self, *args, **kwargs):
            return "test-model-object"

        def generate(self, *args, **kwargs) -> str:
            return "test-response"

    test_llm = TestLLM("test-model")

    with pytest.raises(NotImplementedError, match="does not support multimodal generation"):
        test_llm.generate_multimodal([])


def test_base_llm_analyze_content_not_implemented():
    """Test that analyze_content raises NotImplementedError on base class."""

    class TestLLM(BaseLLM):
        def load_model(self, *args, **kwargs):
            return "test-model-object"

        def generate(self, *args, **kwargs) -> str:
            return "test-response"

    test_llm = TestLLM("test-model")

    with pytest.raises(NotImplementedError, match="does not support content analysis"):
        test_llm.analyze_content(None, "test prompt")


def test_base_llm_generate_image_not_implemented():
    """Test that generate_image raises NotImplementedError on base class."""

    class TestLLM(BaseLLM):
        def load_model(self, *args, **kwargs):
            return "test-model-object"

        def generate(self, *args, **kwargs) -> str:
            return "test-response"

    test_llm = TestLLM("test-model")

    with pytest.raises(NotImplementedError, match="does not support image generation"):
        test_llm.generate_image("test prompt")


def test_base_llm_embed_not_implemented():
    """Test that embed raises NotImplementedError on base class."""

    class TestLLM(BaseLLM):
        def load_model(self, *args, **kwargs):
            return "test-model-object"

        def generate(self, *args, **kwargs) -> str:
            return "test-response"

    test_llm = TestLLM("test-model")

    with pytest.raises(NotImplementedError, match="does not support embeddings"):
        test_llm.embed("test text")
