"""
Available models:
        •	gemini-pro
        •	gemini-1.5-pro-latest
        •	gemini-2.0-flash
        •	gemini-2.0-flash-exp
        •	gemini-2.0-flash-lite-preview-02-05


"""

import json
import os
from typing import List, Literal, Optional, Union

from litellm import completion
from pydantic import BaseModel

from rhesis.sdk.services.base import BaseLLM
from rhesis.sdk.services.utils import validate_llm_response

print(os.getenv("GEMINI_API_KEY"))


PROVIDER = "gemini"
DEFAULT_MODEL_NAME = "gemini-2.0-flash"


class GeminiResponse(BaseModel):
    capital: str
    country: str
    population: int
    big_city: Literal["Yes", "No"]


class ListOfCapitals(BaseModel):
    capitals: List[GeminiResponse]


class GeminiLLM(BaseLLM):
    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, api_key=None, base_url=None, **kwargs):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if self.api_key is None:
            raise ValueError("GEMINI_API_KEY is not set")
        super().__init__(model_name)

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
            api_key=self.api_key,
            *args,
            **kwargs,
        )
        response_content = response.choices[0].message.content
        if schema:
            answer = json.loads(response_content)
            validate_llm_response(answer, schema)
            return answer
        else:
            return response_content


if __name__ == "__main__":
    gemini = GeminiLLM(model_name="gemini-2.0-flash")

    schema = ListOfCapitals.model_json_schema()
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "math_reasoning",
            "schema": schema,
            "strict": True,
        },
    }
    # print(gemini.get_model_name())
    response = gemini.generate(
        "Tell me 10 cities that are big and 10 that are small", schema=schema
    )
    print(response)
    print(type(response))
    # print(type(GeminiResponse.model_validate({"number_of_people": 10, "country": "France"})))
