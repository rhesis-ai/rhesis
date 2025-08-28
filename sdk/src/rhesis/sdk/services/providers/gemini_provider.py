"""
Available models:
        •	gemini-pro
        •	gemini-1.5-pro-latest
        •	gemini-2.0-flash
        •	gemini-2.0-flash-exp
        •	gemini-2.0-flash-lite-preview-02-05


"""

import json
from typing import Literal, Optional, Union

from litellm import completion
from pydantic import BaseModel

from rhesis.sdk.services.base import BaseLLM

PROVIDER = "gemini"


class GeminiResponse(BaseModel):
    question: str
    answer: Literal["yes", "no"]
    reasoning_in_polish: str
    reasoning_in_english: str
    reasoning_in_german: str
    reasoning_in_portuguese: str
    reasoning_in_russian: str


class GeminiLLM(BaseLLM):
    def load_model(self, *args, **kwargs):
        return None  # LiteLLM handles model loading internally

    def generate(
        self, prompt: str, schema: Optional[BaseModel] = None, *args, **kwargs
    ) -> Union[str, BaseModel]:
        messages = [{"role": "user", "content": prompt}]
        response = completion(
            model=f"{PROVIDER}/{self.model_name}",
            messages=messages,
            response_format=schema,
            *args,
            **kwargs,
        )
        response_content = response.choices[0].message.content
        if schema:
            answer_json = json.loads(response_content)
            pydantic_model = schema.model_validate(answer_json)
            return pydantic_model
        else:
            return response_content


if __name__ == "__main__":
    gemini = GeminiLLM(model_name="gemini-2.0-flash")
    # print(gemini.get_model_name())
    response = gemini.generate("Are lions dangerous animals? Answer shortly", schema=GeminiResponse)
    print(response)
    print(type(response))
    # print(type(GeminiResponse.model_validate({"number_of_people": 10, "country": "France"})))
