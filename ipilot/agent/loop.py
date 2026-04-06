from ipilot.agent.context import ContextBuilder
from ipilot.agent.hook import AgentHook
from ipilot.agent.tools.registry import ToolRegistry
from ipilot.providers.base import LLMProvider, LLMResponse
from ipilot.session.manager import SessionManager


class AgentLoop:
    def __init__(
        self,
        provider: LLMProvider,
        workspace,
        session_manager: SessionManager,
        tool_registry: ToolRegistry,
        context_builder: ContextBuilder,
        hooks: list[AgentHook] | None = None,
    ) -> None:
        self.provider = provider
        self.workspace = workspace
        self.session = session_manager
        self.tools = tool_registry
        self.context = context_builder
        self.hooks = hooks or []

    async def _run_before_hooks(self, message: str, session_key: str) -> None:
        for hook in self.hooks:
            await hook.before_iteration({"message": message, "session_key": session_key})

    async def _run_after_hooks(self, message: str, response: LLMResponse, session_key: str) -> None:
        for hook in self.hooks:
            await hook.after_iteration({"message": message, "response": response, "session_key": session_key})

    async def _execute_tool_round(self, messages: list[dict], response: LLMResponse, on_stream=None) -> LLMResponse:
        while response.has_tool_calls:
            for tool_call in response.tool_calls:
                result = await self.tools.execute(tool_call.tool_name, tool_call.arguments)
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.tool_name,
                                    "arguments": str(tool_call.arguments),
                                },
                            },
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.tool_name,
                        "content": str(result),
                    }
                )

            if on_stream is None:
                response = await self.provider.chat(messages=messages, tools=self.tools.get_definitions())
            else:
                response = await self.provider.chat_stream(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    on_delta=on_stream,
                )
        return response

    def _save_turn(self, session_key: str, message: str, response: LLMResponse) -> None:
        session = self.session.get_or_create(session_key)
        session.messages.append({"role": "user", "content": message})
        session.messages.append({"role": "assistant", "content": response.content})
        self.session.save(session)

    async def process_direct(
        self,
        message: str,
        session_key: str,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> LLMResponse:
        await self._run_before_hooks(message, session_key)
        session = self.session.get_or_create(session_key)
        history = session.messages

        messages = self.context.build_messages(history, message, channel=channel, chat_id=chat_id)
        response = await self.provider.chat(
            messages=messages,
            tools=self.tools.get_definitions(),
        )
        response = await self._execute_tool_round(messages, response)
        self._save_turn(session_key, message, response)
        await self._run_after_hooks(message, response, session_key)
        return response

    async def process_direct_stream(
        self,
        message: str,
        session_key: str,
        on_stream=None,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> LLMResponse:
        await self._run_before_hooks(message, session_key)
        session = self.session.get_or_create(session_key)
        history = session.messages

        messages = self.context.build_messages(history, message, channel=channel, chat_id=chat_id)
        response = await self.provider.chat_stream(
            messages=messages,
            tools=self.tools.get_definitions(),
            on_delta=on_stream,
        )
        response = await self._execute_tool_round(messages, response, on_stream=on_stream)
        self._save_turn(session_key, message, response)
        await self._run_after_hooks(message, response, session_key)
        return response

