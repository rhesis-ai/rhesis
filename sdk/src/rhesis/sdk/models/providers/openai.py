from litellm import completion

from rhesis.sdk.models.base import BaseLLM


class OpenAILLM(BaseLLM):
    def load_model(self, *args, **kwargs):
        return None  # LiteLLM handles model loading internally

    def generate(self, prompt: str, *args, **kwargs) -> str:
        messages = [{"role": "user", "content": prompt}]
        response = completion(model=self.model_name, messages=messages, *args, **kwargs)
        return response.choices[0].message.content


if __name__ == "__main__":
    openai = OpenAILLM(model_name="gpt-4")
    print(openai.generate("Hello, how are you?"))
