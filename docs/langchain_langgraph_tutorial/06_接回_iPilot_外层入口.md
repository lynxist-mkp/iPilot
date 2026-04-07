# 第 06 章：接回 iPilot 外层入口

## 本章目标

第 5 章改完以后，内部主链已经变了，但用户真正感知的是这些外部入口：

- `iPilot.run(...)`
- `iPilot.run_stream(...)`
- CLI
- API
- heartbeat
- Twitch

这一章的任务就是把这些入口全部接回新的 LangGraph runtime。

## 本章要改哪些文件

- `ipilot/core.py`
- `ipilot/runtime.py`
- `ipilot/api/server.py`
- `ipilot/cli/commands.py`
- 必要时补测试

## 1. `iPilot` facade 尽量别改风格

`ipilot/core.py` 现在已经很像一个好 facade 了。

这一层最好保持：

```python
class iPilot:
    def __init__(self, loop: AgentLoop):
        self._loop = loop

    @classmethod
    def from_config(cls):
        from ipilot.runtime import build_agent_loop
        return cls(build_agent_loop(load_config()))

    async def run(...):
        return await self._loop.process_direct(...)

    async def run_stream(...):
        return await self._loop.process_direct_stream(...)
```

这层你最多只需要调整返回对象从旧 `LLMResponse` 变成新 `AgentRunResult`。

## 2. CLI 不要感知内部重构

`ipilot/cli/commands.py` 应该尽量不用知道：

- 你是 `create_agent(...)`
- 还是 `StateGraph`
- 还是 `ToolNode`

CLI 只应该知道：

- 拿一个 bot
- 调 `run(...)` 或 `run_stream(...)`
- 打印 `.content`

如果你发现 CLI 需要知道内部 graph 细节，说明封装层做坏了。

## 3. API 也保持最小认知

`ipilot/api/server.py` 当前只做一件事：

- 把最后一条 user message 提给 bot

这一层可以暂时不做结构化升级，继续保持简洁：

```python
response = await bot.run(
    last_user_message,
    session_key="api:default",
    channel="api",
    chat_id="default",
)
```

这一步的核心不是“API 更先进”，而是“新主链已经不影响外部调用方式”。

## 4. heartbeat 和 Twitch 为什么要现在一起接

因为它们代表两类“非交互式入口”：

- heartbeat：系统触发
- Twitch：外部事件触发

只要这两类入口能跑，你的新主链就不是只能在 REPL 里自娱自乐。

heartbeat 继续保留：

```python
await bot.run(
    job.prompt,
    session_key=f"cron:{job.id}",
    channel="cron",
    chat_id=job.id,
)
```

Twitch 继续保留：

```python
response = await self.bot_runner.run(
    inbound.content,
    session_key=inbound.session_key,
    channel=inbound.channel,
    chat_id=inbound.chat_id,
)
```

## 5. 这里最值得补的回归测试

这章最关键的不是新功能测试，而是旧入口不回归。

你至少应该重跑：

```bash
uv run pytest -q tests/test_cli_commands.py tests/test_api_server.py tests/test_twitch_channel.py tests/test_cron_and_heartbeat.py
```

如果这些过不了，就别急着做第 7 章。

## 6. 本章常见坑

### 坑 1：让 API 层直接操作 graph

不要。API 层最多只该看到 `iPilot` facade。

### 坑 2：在 Twitch / heartbeat 层重新造 session 管理

不要。`session_key -> thread_id` 已经够用了。

### 坑 3：让 `.content` 消失

对外层来说，`.content` 仍然是最低摩擦接口。不要为了“纯粹”把外部适配层全重写。

## 7. 本章验证

除了跑回归测试，再做两个手工验证：

### 验证 1：CLI

```bash
uv run ipilot agent -m "Reply with exactly: hello"
```

### 验证 2：API

```bash
uv run uvicorn ipilot.api.server:app --reload --port 8900
curl http://127.0.0.1:8900/health
```

通过标准：

- `iPilot.run(...)` / `run_stream(...)` 仍然是统一入口
- CLI / API / heartbeat / Twitch 都接在新 graph runtime 上
- 外围层不需要理解 LangGraph 内部细节
