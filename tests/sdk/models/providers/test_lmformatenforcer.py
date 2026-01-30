from unittest.mock import Mock, patch

import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("lmformatenforcer")

import torch
from pydantic import BaseModel

from rhesis.sdk.errors import (
    HUGGINGFACE_MODEL_NOT_LOADED,
    MODEL_RELOAD_WARNING,
    NO_MODEL_NAME_PROVIDED,
    WARNING_TOKENIZER_ALREADY_LOADED_RELOAD,
)
from rhesis.sdk.models import LMFormatEnforcerLLM


class TestLMFormatEnforcerLLM:
    def test_init_without_auto_loading_and_no_defaults(self):
        """Should initialize without auto-loading and no defaults"""
        model_name = "provider/model"
        llm = LMFormatEnforcerLLM(model_name, auto_loading=False)

        assert llm.model_name == model_name
        assert llm.model is None
        assert llm.tokenizer is None
        assert llm.device is None
        assert llm.generate_kwargs is None

    def test_init_without_auto_loading_and_with_defaults(self):
        """Should initialize without auto-loading and with defaults"""
        model_name = "provider/model"
        generate_kwargs = {"temperature": 0.7}

        llm = LMFormatEnforcerLLM(model_name, auto_loading=False, generate_kwargs=generate_kwargs)

        assert llm.model_name == model_name
        assert llm.model is None
        assert llm.tokenizer is None
        assert llm.device is None
        assert llm.generate_kwargs is generate_kwargs

    @patch("rhesis.sdk.models.providers.lmformatenforcer.torch.device")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoModelForCausalLM")
    def test_init_with_auto_loading_and_no_defaults(
        self, mock_auto_model, mock_auto_tokenizer, mock_torch_device
    ):
        """Should auto-load model when auto_loading=True and no defaults"""
        mock_model = Mock(spec=["device", "generate", "parameters", "buffers"])
        mock_model.device = torch.device("cpu")
        mock_tokenizer = Mock()
        mock_device = Mock()

        mock_auto_model.from_pretrained.return_value = mock_model
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer
        mock_torch_device.return_value = mock_device

        model_name = "provider/model"
        llm = LMFormatEnforcerLLM(model_name, auto_loading=True)

        assert llm.model_name == model_name
        assert llm.model is mock_model
        assert llm.tokenizer is mock_tokenizer
        assert llm.device == mock_model.device
        assert llm.generate_kwargs is None
        mock_auto_model.from_pretrained.assert_called_once_with(model_name, device_map="auto")
        mock_auto_tokenizer.from_pretrained.assert_called_once_with(model_name)

    @patch("rhesis.sdk.models.providers.lmformatenforcer.torch.device")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoModelForCausalLM")
    def test_init_with_auto_loading_and_with_defaults(
        self, mock_auto_model, mock_auto_tokenizer, mock_torch_device
    ):
        """Should auto-load model when auto_loading=True and defaults provided"""
        mock_model = Mock(spec=["device", "generate", "parameters", "buffers"])
        mock_model.device = torch.device("cpu")
        mock_tokenizer = Mock()
        mock_device = Mock()

        mock_auto_model.from_pretrained.return_value = mock_model
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer
        mock_torch_device.return_value = mock_device

        model_name = "provider/model"
        generate_kwargs = {"temperature": 0.7}
        llm = LMFormatEnforcerLLM(model_name, auto_loading=True, generate_kwargs=generate_kwargs)

        assert llm.model_name == model_name
        assert llm.model is mock_model
        assert llm.tokenizer is mock_tokenizer
        assert llm.device == mock_model.device
        assert llm.generate_kwargs is generate_kwargs
        mock_auto_model.from_pretrained.assert_called_once_with(model_name, device_map="auto")
        mock_auto_tokenizer.from_pretrained.assert_called_once_with(model_name)

    def test_init_raises_with_no_model_name(self):
        """Should raise ValueError if model_name is None"""
        with pytest.raises(ValueError) as excinfo:
            LMFormatEnforcerLLM(None)
        assert str(excinfo.value) == NO_MODEL_NAME_PROVIDED

    def test_init_raises_with_empty_string(self):
        """Should raise ValueError if model_name is empty string"""
        with pytest.raises(ValueError) as excinfo:
            LMFormatEnforcerLLM("")
        assert str(excinfo.value) == NO_MODEL_NAME_PROVIDED

    def setup_model_with_mocks(self, has_chat_template=True):
        """Helper to create a LMFormatEnforcerLLM with mocked model + tokenizer"""
        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)
        llm.device = torch.device("cpu")

        # Mock tokenizer
        mock_tokenizer = Mock()
        mock_tokenizer.chat_template = "template" if has_chat_template else None
        mock_tokenizer.eos_token_id = 42
        mock_tokenizer.decode.return_value = "Generated response"

        # Create actual dict with tensors
        inputs = {
            "input_ids": torch.tensor([[1, 995, 460, 10032, 13, 13, 22467, 528, 264, 13015]]),
            "attention_mask": torch.tensor([[1, 1, 1, 1, 1, 1, 1, 1, 1, 1]]),
        }

        if has_chat_template:
            mock_tokenizer.apply_chat_template.return_value = inputs
        else:
            mock_tokenizer.return_value = inputs

        # Mock model
        mock_model = Mock()
        output_tensor = torch.tensor([[101, 102, 103, 104, 105]])
        mock_model.generate.return_value = output_tensor

        llm.tokenizer = mock_tokenizer
        llm.model = mock_model

        return llm, mock_model, mock_tokenizer

    def test_generate_without_chat_template(self):
        """Should generate when tokenizer has no chat_template"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks(has_chat_template=False)
        result = llm.generate("Hello, world!")
        assert result == "Generated response"
        mock_tokenizer.assert_called_once_with("Hello, world!", return_tensors="pt")
        mock_model.generate.assert_called_once()
        mock_tokenizer.decode.assert_called_once()

    def test_generate_with_chat_template_and_system_prompt(self):
        """Should use apply_chat_template when chat_template is available and system_prompt given"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks(has_chat_template=True)
        result = llm.generate("Hello?", system_prompt="You are a helpful assistant.")
        assert result == "Generated response"
        mock_tokenizer.apply_chat_template.assert_called_once()
        mock_model.generate.assert_called_once()
        mock_tokenizer.decode.assert_called_once()

    def test_generate_with_chat_template_no_system_prompt(self):
        """Should use apply_chat_template when chat_template is available and no system_prompt given"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks(has_chat_template=True)
        result = llm.generate("Hello?")
        assert result == "Generated response"
        mock_tokenizer.apply_chat_template.assert_called_once()
        mock_model.generate.assert_called_once()
        mock_tokenizer.decode.assert_called_once()

    def test_generate_with_system_prompt_no_chat_template(self):
        """Should prepend system_prompt when chat_template is missing"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks(has_chat_template=False)
        prompt = "Hello?"
        system_prompt = "You are helpful."
        result = llm.generate(prompt, system_prompt=system_prompt)
        assert result == "Generated response"
        expected_input = f"{system_prompt}\n\n{prompt}"
        mock_tokenizer.assert_called_once_with(expected_input, return_tensors="pt")

    def test_generate_merges_generate_kwargs(self):
        """Should merge generate_kwargs with passed kwargs, allowing override"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()
        llm.generate_kwargs = {"temperature": 0.7, "max_new_tokens": 10}
        result = llm.generate("Test prompt", max_new_tokens=20)
        assert result == "Generated response"
        _, kwargs = mock_model.generate.call_args
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_new_tokens"] == 20

    def test_generate_respects_only_generate_kwargs(self):
        """Should pass only generate_kwargs if no kwargs given"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()
        llm.generate_kwargs = {"top_p": 0.9}
        result = llm.generate("Test prompt")
        assert result == "Generated response"
        _, kwargs = mock_model.generate.call_args
        assert kwargs["top_p"] == 0.9

    def test_generate_without_generate_kwargs(self):
        """Should work when generate_kwargs is None and no kwargs provided"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()
        llm.generate_kwargs = None
        result = llm.generate("Just a plain test")
        assert result == "Generated response"
        mock_model.generate.assert_called_once()

    def test_generate_returns_stripped_output(self):
        """Should strip whitespace from decoded text"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()
        mock_tokenizer.decode.return_value = "   padded text   "
        result = llm.generate("Strip test")
        assert result == "padded text"

    # Tests for model_path functionality
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoModelForCausalLM")
    def test_load_model_with_model_path(self, mock_auto_model, mock_auto_tokenizer):
        """Should load model from local path when model_path is provided"""
        mock_model = Mock(spec=["device", "generate", "parameters", "buffers"])
        mock_model.device = torch.device("cpu")
        mock_tokenizer = Mock()

        mock_auto_model.from_pretrained.return_value = mock_model
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        llm = LMFormatEnforcerLLM(
            "provider/model", auto_loading=False, model_path="/local/path/to/model"
        )
        llm.load_model()

        # Should use model_path instead of model_name
        mock_auto_model.from_pretrained.assert_called_once()
        call_args = mock_auto_model.from_pretrained.call_args
        assert call_args[0][0] == "/local/path/to/model"
        assert call_args[1]["device_map"] == "auto"
        assert call_args[1]["trust_remote_code"] is True

        # Tokenizer should also use model_path
        mock_auto_tokenizer.from_pretrained.assert_called_once_with("/local/path/to/model")

    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoModelForCausalLM")
    def test_load_model_without_model_path(self, mock_auto_model, mock_auto_tokenizer):
        """Should load model from HuggingFace Hub when model_path is not provided"""
        mock_model = Mock(spec=["device", "generate", "parameters", "buffers"])
        mock_model.device = torch.device("cpu")
        mock_tokenizer = Mock()

        mock_auto_model.from_pretrained.return_value = mock_model
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)
        llm.load_model()

        # Should use model_name
        mock_auto_model.from_pretrained.assert_called_once()
        call_args = mock_auto_model.from_pretrained.call_args
        assert call_args[0][0] == "provider/model"
        assert (
            "trust_remote_code" not in call_args[1]
            or call_args[1].get("trust_remote_code") is not True
        )

    # Tests for gpu_only functionality
    @patch("rhesis.sdk.models.providers.lmformatenforcer.torch.cuda.is_available")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoModelForCausalLM")
    def test_load_model_gpu_only_without_cuda(
        self, mock_auto_model, mock_auto_tokenizer, mock_cuda_available
    ):
        """Should raise RuntimeError when gpu_only=True but CUDA is not available"""
        mock_cuda_available.return_value = False

        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False, gpu_only=True)
        with pytest.raises(RuntimeError, match="gpu_only=True but CUDA is not available"):
            llm.load_model()

    @patch("rhesis.sdk.models.providers.lmformatenforcer.torch.cuda.is_available")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoModelForCausalLM")
    def test_load_model_gpu_only_with_cuda(
        self, mock_auto_model, mock_auto_tokenizer, mock_cuda_available
    ):
        """Should load model with gpu_only=True when CUDA is available"""
        mock_cuda_available.return_value = True
        mock_model = Mock(spec=["device", "generate", "parameters", "buffers", "hf_device_map"])
        mock_model.device = torch.device("cuda:0")
        mock_model.hf_device_map = {"layer1": "cuda:0", "layer2": "cuda:0"}
        mock_tokenizer = Mock()

        mock_auto_model.from_pretrained.return_value = mock_model
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False, gpu_only=True)
        llm.load_model()

        call_args = mock_auto_model.from_pretrained.call_args
        assert call_args[1]["device_map"] == "auto"

    @patch("rhesis.sdk.models.providers.lmformatenforcer.torch.cuda.is_available")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoModelForCausalLM")
    def test_load_model_gpu_only_with_cpu_offload(
        self, mock_auto_model, mock_auto_tokenizer, mock_cuda_available
    ):
        """Should raise RuntimeError when gpu_only=True but model is offloaded to CPU"""
        mock_cuda_available.return_value = True
        mock_model = Mock(spec=["device", "generate", "parameters", "buffers", "hf_device_map"])
        mock_model.device = torch.device("cuda:0")
        # Simulate CPU offloading
        mock_model.hf_device_map = {"layer1": "cuda:0", "layer2": "cpu"}
        mock_tokenizer = Mock()

        mock_auto_model.from_pretrained.return_value = mock_model
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False, gpu_only=True)
        with pytest.raises(RuntimeError, match="gpu_only=True but model has layers offloaded to"):
            llm.load_model()

    # Tests for hf_device_map handling (multi-device models)
    @patch("rhesis.sdk.models.providers.lmformatenforcer.torch.device")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoModelForCausalLM")
    def test_load_model_with_hf_device_map(
        self, mock_auto_model, mock_auto_tokenizer, mock_torch_device
    ):
        """Should handle multi-device models with hf_device_map"""
        mock_model = Mock(spec=["device", "generate", "parameters", "buffers", "hf_device_map"])
        mock_model.device = torch.device("cuda:0")
        mock_model.hf_device_map = {"layer1": "cuda:0", "layer2": "cuda:1"}
        mock_tokenizer = Mock()
        mock_device = torch.device("cuda:0")

        mock_auto_model.from_pretrained.return_value = mock_model
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer
        mock_torch_device.return_value = mock_device

        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)
        llm.load_model()

        # Should use device from first layer in hf_device_map
        assert llm.device == mock_device

    @patch("rhesis.sdk.models.providers.lmformatenforcer.torch.device")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoModelForCausalLM")
    def test_load_model_without_hf_device_map(
        self, mock_auto_model, mock_auto_tokenizer, mock_torch_device
    ):
        """Should use model.device when hf_device_map is not present"""
        mock_model = Mock(spec=["device", "generate", "parameters", "buffers"])
        mock_model.device = torch.device("cpu")
        mock_tokenizer = Mock()

        mock_auto_model.from_pretrained.return_value = mock_model
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)
        llm.load_model()

        # Should use model.device directly
        assert llm.device == mock_model.device

    # Tests for load_kwargs
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoModelForCausalLM")
    def test_load_model_with_load_kwargs(self, mock_auto_model, mock_auto_tokenizer):
        """Should pass load_kwargs to from_pretrained"""
        mock_model = Mock(spec=["device", "generate", "parameters", "buffers"])
        mock_model.device = torch.device("cpu")
        mock_tokenizer = Mock()

        mock_auto_model.from_pretrained.return_value = mock_model
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        load_kwargs = {"torch_dtype": torch.float16, "low_cpu_mem_usage": True}
        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False, load_kwargs=load_kwargs)
        llm.load_model()

        call_args = mock_auto_model.from_pretrained.call_args
        assert call_args[1]["torch_dtype"] == torch.float16
        assert call_args[1]["low_cpu_mem_usage"] is True
        assert call_args[1]["device_map"] == "auto"

    # Tests for reload warnings
    @patch("builtins.print")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoModelForCausalLM")
    def test_load_model_warns_on_model_reload(
        self, mock_auto_model, mock_auto_tokenizer, mock_print
    ):
        """Should warn when reloading an already loaded model"""
        mock_model = Mock(spec=["device", "generate", "parameters", "buffers"])
        mock_model.device = torch.device("cpu")
        mock_tokenizer = Mock()

        mock_auto_model.from_pretrained.return_value = mock_model
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)
        llm.model = Mock()  # Simulate already loaded model
        llm.load_model()

        mock_print.assert_any_call(MODEL_RELOAD_WARNING.format("provider/model"))

    @patch("builtins.print")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.AutoModelForCausalLM")
    def test_load_model_warns_on_tokenizer_reload(
        self, mock_auto_model, mock_auto_tokenizer, mock_print
    ):
        """Should warn when reloading an already loaded tokenizer"""
        mock_model = Mock(spec=["device", "generate", "parameters", "buffers"])
        mock_model.device = torch.device("cpu")
        mock_tokenizer = Mock()

        mock_auto_model.from_pretrained.return_value = mock_model
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)
        llm.tokenizer = Mock()  # Simulate already loaded tokenizer
        llm.load_model()

        mock_print.assert_any_call(WARNING_TOKENIZER_ALREADY_LOADED_RELOAD.format("provider/model"))

    # Tests for memory calculation
    def test_get_model_memory_gb_without_model(self):
        """Should return 0.0 when model is not loaded"""
        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)
        assert llm._get_model_memory_gb() == 0.0

    def test_get_model_memory_gb_with_model(self):
        """Should calculate memory footprint when model is loaded"""
        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)

        # Create tensors large enough to result in non-zero GB
        num_elements = (10 * 1024 * 1024) // 4  # 10MB / 4 bytes per float32
        param1 = torch.randn(num_elements // 2)  # ~5MB
        param2 = torch.randn(num_elements // 2)  # ~5MB
        buffer1 = torch.randn(1000)  # Small buffer

        # Create a mock model that returns these tensors
        mock_model = Mock()
        mock_model.parameters.return_value = [param1, param2]
        mock_model.buffers.return_value = [buffer1]

        llm.model = mock_model

        memory_gb = llm._get_model_memory_gb()
        assert memory_gb > 0
        assert isinstance(memory_gb, float)
        assert memory_gb >= 0.010

    def test_get_model_memory_gb_handles_exception(self):
        """Should return 0.0 when memory calculation fails"""
        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)
        mock_model = Mock()
        mock_model.parameters.side_effect = Exception("Error calculating memory")
        llm.model = mock_model

        assert llm._get_model_memory_gb() == 0.0

    # Tests for constrained schema support (LMFormatEnforcer-specific)
    @patch("rhesis.sdk.models.providers.lmformatenforcer.JsonSchemaParser")
    @patch(
        "rhesis.sdk.models.providers.lmformatenforcer.build_transformers_prefix_allowed_tokens_fn"
    )
    def test_generate_with_schema_uses_constrained_decoding(self, mock_build_fn, mock_json_parser):
        """Should use constrained decoding when schema is provided"""

        class TestSchema(BaseModel):
            name: str
            age: int

        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()
        # Mock decode to return valid JSON matching schema
        mock_tokenizer.decode.return_value = '{"name": "John", "age": 30}'

        # Mock the constrained decoding components
        mock_parser_instance = Mock()
        mock_json_parser.return_value = mock_parser_instance
        mock_prefix_fn = Mock()
        mock_build_fn.return_value = mock_prefix_fn

        result = llm.generate("Generate person data", schema=TestSchema)

        assert isinstance(result, dict)
        assert result["name"] == "John"
        assert result["age"] == 30

        # Verify JsonSchemaParser was created with the schema
        mock_json_parser.assert_called_once()
        # Verify constrained decoding function was built
        mock_build_fn.assert_called_once()
        # Verify prefix_allowed_tokens_fn was passed to generate
        _, kwargs = mock_model.generate.call_args
        assert "prefix_allowed_tokens_fn" in kwargs

    def test_generate_with_schema_guarantees_valid_json(self):
        """Should always return valid JSON matching the schema (guaranteed by library)"""

        class TestSchema(BaseModel):
            name: str
            age: int

        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()
        # The library guarantees valid JSON, so we mock that behavior
        mock_tokenizer.decode.return_value = '{"name": "Alice", "age": 25}'

        result = llm.generate("Generate person data", schema=TestSchema)

        # Should successfully parse and validate
        assert isinstance(result, dict)
        assert "name" in result
        assert "age" in result
        assert isinstance(result["name"], str)
        assert isinstance(result["age"], int)

    def test_generate_without_schema_no_constrained_decoding(self):
        """Should not use constrained decoding when no schema is provided"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()

        result = llm.generate("Generate text")

        # Verify no constrained decoding was used
        _, kwargs = mock_model.generate.call_args
        assert "prefix_allowed_tokens_fn" not in kwargs
        assert result == "Generated response"

    # Tests for metadata tracking
    def test_generate_stores_metadata(self):
        """Should store generation metadata in last_generation_metadata"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()

        # Setup mocks to return predictable values
        input_tensor = torch.tensor([[1, 2, 3, 4, 5]])
        output_tensor = torch.tensor([[1, 2, 3, 4, 5, 6, 7, 8]])  # 3 more tokens than input

        mock_tokenizer.apply_chat_template.return_value = {
            "input_ids": input_tensor,
            "attention_mask": torch.tensor([[1, 1, 1, 1, 1]]),
        }
        mock_model.generate.return_value = output_tensor

        llm.generate("Test prompt")

        assert llm.last_generation_metadata is not None
        assert "input_tokens" in llm.last_generation_metadata
        assert "output_tokens" in llm.last_generation_metadata
        assert "generation_time_seconds" in llm.last_generation_metadata
        assert "model_memory_gb" in llm.last_generation_metadata
        assert llm.last_generation_metadata["input_tokens"] == 5
        assert llm.last_generation_metadata["output_tokens"] == 3

    def test_generate_sets_default_max_new_tokens(self):
        """Should set default max_new_tokens to 2048 if not provided"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()
        llm.generate("Test prompt")

        call_args = mock_model.generate.call_args
        assert call_args[1]["max_new_tokens"] == 2048

    def test_generate_respects_custom_max_new_tokens(self):
        """Should use custom max_new_tokens when provided"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()
        llm.generate("Test prompt", max_new_tokens=100)

        call_args = mock_model.generate.call_args
        assert call_args[1]["max_new_tokens"] == 100

    # Tests for error handling
    def test_generate_raises_when_model_not_loaded(self):
        """Should raise RuntimeError when model is not loaded"""
        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)

        with pytest.raises(RuntimeError) as exc_info:
            llm.generate("Test prompt")
        assert str(exc_info.value) == HUGGINGFACE_MODEL_NOT_LOADED

    def test_generate_raises_when_tokenizer_not_loaded(self):
        """Should raise RuntimeError when tokenizer is not loaded"""
        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)
        llm.model = Mock()  # Model loaded but tokenizer not

        with pytest.raises(RuntimeError) as exc_info:
            llm.generate("Test prompt")
        assert str(exc_info.value) == HUGGINGFACE_MODEL_NOT_LOADED

    # Tests for unload_model
    @patch("rhesis.sdk.models.providers.lmformatenforcer.torch.cuda.empty_cache")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.gc.collect")
    def test_unload_model(self, mock_gc_collect, mock_empty_cache):
        """Should unload model and tokenizer and free memory"""
        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)
        llm.model = Mock()
        llm.tokenizer = Mock()

        initial_empty_cache_count = mock_empty_cache.call_count
        initial_gc_count = mock_gc_collect.call_count

        llm.unload_model()

        assert llm.model is None
        assert llm.tokenizer is None
        # Should attempt to free GPU cache (even if no GPU) - called twice in unload_model
        assert mock_empty_cache.call_count >= initial_empty_cache_count + 2
        # Should call gc.collect at least once
        assert mock_gc_collect.call_count >= initial_gc_count + 1

    @patch("rhesis.sdk.models.providers.lmformatenforcer.torch.cuda.empty_cache")
    @patch("rhesis.sdk.models.providers.lmformatenforcer.gc.collect")
    def test_unload_model_handles_exceptions(self, mock_gc_collect, mock_empty_cache):
        """Should handle exceptions during unload gracefully"""
        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)
        mock_model = Mock()
        mock_model.cpu.side_effect = Exception("Error moving to CPU")
        llm.model = mock_model
        llm.tokenizer = Mock()

        # Should not raise exception
        llm.unload_model()

        # Should still attempt cleanup
        assert mock_empty_cache.call_count == 2
        mock_gc_collect.assert_called_once()

    def test_unload_model_with_state_dict(self):
        """Should clear state_dict when unloading model"""
        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)
        mock_model = Mock()
        mock_state_dict = {"layer1": Mock(), "layer2": Mock()}
        mock_model.state_dict.return_value = mock_state_dict
        llm.model = mock_model

        llm.unload_model()

        assert llm.model is None
        # Verify state_dict was accessed
        mock_model.state_dict.assert_called_once()

    # Tests for custom_results_dir
    def test_init_with_custom_results_dir(self):
        """Should store custom_results_dir when provided"""
        llm = LMFormatEnforcerLLM(
            "provider/model", auto_loading=False, custom_results_dir="/custom/path"
        )
        assert llm.custom_results_dir == "/custom/path"

    def test_init_without_custom_results_dir(self):
        """Should set custom_results_dir to None when not provided"""
        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)
        assert llm.custom_results_dir is None

    # Tests for generate_batch (not implemented)
    def test_generate_batch_raises_not_implemented(self):
        """Should raise NotImplementedError for batch generation"""
        llm = LMFormatEnforcerLLM("provider/model", auto_loading=False)

        with pytest.raises(NotImplementedError):
            llm.generate_batch(["prompt1", "prompt2"])
