"""
Available models:
        •	gemini-pro
        •	gemini-1.5-pro-latest
        •	gemini-2.0-flash
        •	gemini-2.0-flash-exp
        •	gemini-2.0-flash-lite-preview-02-05


"""

from litellm import completion

from rhesis.sdk.services.base import BaseLLM

PROVIDER = "gemini"


class GeminiLLM(BaseLLM):
    def load_model(self, *args, **kwargs):
        return None  # LiteLLM handles model loading internally

    def generate(self, prompt: str, *args, **kwargs) -> str:
        messages = [{"role": "user", "content": prompt}]
        response = completion(
            model=f"{PROVIDER}/{self.model_name}",
            messages=messages,
            *args,
            **kwargs,
        )
        return response.choices[0].message.content


if __name__ == "__main__":
    gemini = GeminiLLM(model_name="gemini-1.5-pro-latest")
    # print(gemini.get_model_name())
    print(gemini.generate("Hello, how are you?"))
