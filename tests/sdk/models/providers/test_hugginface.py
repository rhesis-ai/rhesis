from unittest.mock import Mock, patch

import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")

import torch

from rhesis.sdk.errors import NO_MODEL_NAME_PROVIDED
from rhesis.sdk.models import HuggingFaceLLM


class TestHuggingFaceLLM:
    def test_init_without_auto_loading_and_no_defaults(self):
        """Should initialize without auto-loading and no defaults"""
        model_name = "provider/model"
        llm = HuggingFaceLLM(model_name, auto_loading=False)

        assert llm.model_name == model_name
        assert llm.model is None
        assert llm.tokenizer is None
        assert llm.device is None
        assert llm.default_kwargs is None

    def test_init_without_auto_loading_and_with_defaults(self):
        """Should initialize without auto-loading and with defaults"""
        model_name = "provider/model"
        default_kwargs = {"temperature": 0.7}

        llm = HuggingFaceLLM(model_name, auto_loading=False, default_kwargs=default_kwargs)

        assert llm.model_name == model_name
        assert llm.model is None
        assert llm.tokenizer is None
        assert llm.device is None
        assert llm.default_kwargs is default_kwargs

    @patch("rhesis.sdk.models.providers.huggingface.torch.device")
    @patch("rhesis.sdk.models.providers.huggingface.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.huggingface.AutoModelForCausalLM")
    def test_init_with_auto_loading_and_no_defaults(
        self, mock_auto_model, mock_auto_tokenizer, mock_torch_device
    ):
        """Should auto-load model when auto_loading=True and no defaults"""
        mock_model = Mock()
        mock_tokenizer = Mock()
        mock_device = Mock()

        mock_auto_model.from_pretrained.return_value = mock_model
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer
        mock_torch_device.return_value = mock_device

        model_name = "provider/model"
        llm = HuggingFaceLLM(model_name, auto_loading=True)

        assert llm.model_name == model_name
        assert llm.model is mock_model
        assert llm.tokenizer is mock_tokenizer
        assert llm.device is mock_device
        assert llm.default_kwargs is None
        mock_auto_model.from_pretrained.assert_called_once_with(model_name)
        mock_auto_tokenizer.from_pretrained.assert_called_once_with(model_name)

    @patch("rhesis.sdk.models.providers.huggingface.torch.device")
    @patch("rhesis.sdk.models.providers.huggingface.AutoTokenizer")
    @patch("rhesis.sdk.models.providers.huggingface.AutoModelForCausalLM")
    def test_init_with_auto_loading_and_with_defaults(
        self, mock_auto_model, mock_auto_tokenizer, mock_torch_device
    ):
        """Should auto-load model when auto_loading=True and defaults provided"""
        mock_model = Mock()
        mock_tokenizer = Mock()
        mock_device = Mock()

        mock_auto_model.from_pretrained.return_value = mock_model
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer
        mock_torch_device.return_value = mock_device

        model_name = "provider/model"
        default_kwargs = {"temperature": 0.7}
        llm = HuggingFaceLLM(model_name, auto_loading=True, default_kwargs=default_kwargs)

        assert llm.model_name == model_name
        assert llm.model is mock_model
        assert llm.tokenizer is mock_tokenizer
        assert llm.device is mock_device
        assert llm.default_kwargs is default_kwargs
        mock_auto_model.from_pretrained.assert_called_once_with(model_name)
        mock_auto_tokenizer.from_pretrained.assert_called_once_with(model_name)

    def test_init_raises_with_no_model_name(self):
        """Should raise ValueError if model_name is None"""
        with pytest.raises(ValueError) as excinfo:
            HuggingFaceLLM(None)
        assert str(excinfo.value) == NO_MODEL_NAME_PROVIDED

    def test_init_raises_with_empty_string(self):
        """Should raise ValueError if model_name is empty string"""
        with pytest.raises(ValueError) as excinfo:
            HuggingFaceLLM("")
        assert str(excinfo.value) == NO_MODEL_NAME_PROVIDED

    def setup_model_with_mocks(self, has_chat_template=True):
        """Helper to create a HuggingFaceLLM with mocked model + tokenizer"""
        llm = HuggingFaceLLM("provider/model", auto_loading=False)
        llm.device = "cpu"

        # Mock tokenizer
        mock_tokenizer = Mock()
        mock_tokenizer.chat_template = "template" if has_chat_template else None
        mock_tokenizer.eos_token_id = 42
        mock_tokenizer.decode.return_value = "Generated response"

        inputs = {
            "input_ids": torch.tensor([[1, 995, 460, 10032, 13, 13, 22467, 528, 264, 13015]]),
            "attention_mask": torch.tensor([[1, 1, 1, 1, 1, 1, 1, 1, 1, 1]]),
        }

        # the object returned when calling tokenizer(...)
        tokenizer_call_ret = Mock()
        tokenizer_call_ret.to.return_value = inputs
        if has_chat_template:
            mock_tokenizer.apply_chat_template.return_value = tokenizer_call_ret
        else:
            mock_tokenizer.return_value = tokenizer_call_ret

        # Mock model
        mock_model = Mock()
        # Return a tensor-like object with shape attribute
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

    def test_generate_merges_default_kwargs(self):
        """Should merge default_kwargs with passed kwargs, allowing override"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()
        llm.default_kwargs = {"temperature": 0.7, "max_new_tokens": 10}
        result = llm.generate("Test prompt", max_new_tokens=20)
        assert result == "Generated response"
        _, kwargs = mock_model.generate.call_args
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_new_tokens"] == 20

    def test_generate_respects_only_default_kwargs(self):
        """Should pass only default_kwargs if no kwargs given"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()
        llm.default_kwargs = {"top_p": 0.9}
        result = llm.generate("Test prompt")
        assert result == "Generated response"
        _, kwargs = mock_model.generate.call_args
        assert kwargs["top_p"] == 0.9

    def test_generate_without_default_kwargs(self):
        """Should work when default_kwargs is None and no kwargs provided"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()
        llm.default_kwargs = None
        result = llm.generate("Just a plain test")
        assert result == "Generated response"
        mock_model.generate.assert_called_once()

    def test_generate_returns_stripped_output(self):
        """Should strip whitespace from decoded text"""
        llm, mock_model, mock_tokenizer = self.setup_model_with_mocks()
        mock_tokenizer.decode.return_value = "   padded text   "
        result = llm.generate("Strip test")
        assert result == "padded text"
