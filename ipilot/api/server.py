from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from ipilot import iPilot
from ipilot.config.loader import load_config


app = FastAPI()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/models")
def list_models():
    config = load_config()
    return {
        "data": [
            {
                "id": config.agents.defaults.model,
                "object": "model",
            }
        ]
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    bot = iPilot.from_config()
    user_messages = [message for message in request.messages if message.role == "user"]
    last_user_message = user_messages[-1].content if user_messages else ""
    response = await bot.run(
        last_user_message,
        session_key="api:default",
        channel="api",
        chat_id="default",
    )
    return {
        "id": "chatcmpl-demo",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response.content,
                },
                "finish_reason": response.finish_reason,
            }
        ],
    }

