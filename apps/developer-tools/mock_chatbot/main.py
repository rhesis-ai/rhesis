from faker import Faker
from fastapi import FastAPI
from pydantic import BaseModel

HOST = "0.0.0.0"
PORT = 18090

app = FastAPI(title="Mock Chatbot")
fake = Faker()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    message: str
    response: str


@app.post("/")
async def chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse(message=request.message, response=fake.paragraph(nb_sentences=3))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
