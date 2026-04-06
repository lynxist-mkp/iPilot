import asyncio
import inspect
import json
from typing import Any

from openai import AsyncOpenAI

from ipilot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        api_base: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    async def _create_with_retry(self, **kwargs):
        last_error = None
        for delay in [0, 1, 2, 4]:
            try:
                if delay:
                    await asyncio.sleep(delay)
                return await self.client.chat.completions.create(**kwargs)
            except Exception as exc:
                last_error = exc
        raise last_error

    @staticmethod
    def _normalize_tool_calls(raw_tool_calls) -> list[ToolCallRequest]:
        tool_calls: list[ToolCallRequest] = []
        for tool_call in raw_tool_calls or []:
            raw_arguments = tool_call.function.arguments or "{}"
            tool_calls.append(
                ToolCallRequest(
                    id=tool_call.id,
                    tool_name=tool_call.function.name,
                    arguments=json.loads(raw_arguments),
                )
            )
        return tool_calls

    def _normalize_response(self, response) -> LLMResponse:
        choice = response.choices[0]
        message = choice.message
        return LLMResponse(
            content=message.content,
            tool_calls=self._normalize_tool_calls(message.tool_calls),
            finish_reason=choice.finish_reason or "stop",
        )

    @staticmethod
    async def _emit_delta(on_delta, delta: str) -> None:
        if on_delta is None:
            return
        result = on_delta(delta)
        if inspect.isawaitable(result):
            await result

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        response = await self._create_with_retry(
            model=model or self.model,
            messages=messages,
            tools=tools,
        )
        return self._normalize_response(response)

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        on_delta=None,
    ) -> LLMResponse:
        stream = await self._create_with_retry(
            model=model or self.model,
            messages=messages,
            tools=tools,
            stream=True,
        )

        content_parts: list[str] = []
        tool_call_parts: dict[int, dict[str, Any]] = {}
        finish_reason = "stop"

        async for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta

            text = getattr(delta, "content", None)
            if text:
                content_parts.append(text)
                await self._emit_delta(on_delta, text)

            for tool_call in getattr(delta, "tool_calls", None) or []:
                current = tool_call_parts.setdefault(
                    tool_call.index,
                    {"id": "", "name": "", "arguments": []},
                )
                if getattr(tool_call, "id", None):
                    current["id"] = tool_call.id
                function = getattr(tool_call, "function", None)
                if function is not None:
                    if getattr(function, "name", None):
                        current["name"] = function.name
                    if getattr(function, "arguments", None):
                        current["arguments"].append(function.arguments)

            if choice.finish_reason:
                finish_reason = choice.finish_reason

        tool_calls = [
            ToolCallRequest(
                id=item["id"],
                tool_name=item["name"],
                arguments=json.loads("".join(item["arguments"]) or "{}"),
            )
            for _, item in sorted(tool_call_parts.items())
            if item["name"]
        ]
        return LLMResponse(
            content="".join(content_parts) or None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
        )

