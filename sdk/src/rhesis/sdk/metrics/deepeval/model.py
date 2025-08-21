# Import DeepEvalBaseLLM for proper custom model implementation

from deepeval.models import DeepEvalBaseLLM

from rhesis.sdk.services.model_factory import ModelConfig, ModelFactory, ModelType


class DeepEvalModelWrapper(DeepEvalBaseLLM):
    def __init__(self, config: ModelConfig) -> None:
        if config.model_name is None:
            self._model = ModelFactory.create_default_model(config.model_type)
        else:
            self._model = ModelFactory.create_model(config)

    def load_model(self, *args, **kwargs):
        return self._model.load_model(*args, **kwargs)

    def generate(self, prompt: str) -> str:
        return self._model.generate(prompt, response_format="text")

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self, *args, **kwargs) -> str:
        return self._model.get_model_name(*args, **kwargs)


def get_model_from_config(config: ModelConfig) -> DeepEvalModelWrapper:
    return DeepEvalModelWrapper(config)


if __name__ == "__main__":
    config = ModelConfig(model_type=ModelType.RHESIS, model_name="rhesis-default")
    model = DeepEvalModelWrapper(config)
    print(model.generate(prompt="What is the capital of China?"))
