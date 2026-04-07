# iPilot

一个按教程逐章重建的轻量 agent 框架，目前已经补齐 10-13 章的最小实战链路：

- 统一 CLI / SDK / API 主链
- provider retry 与 streaming
- session 持久化
- cron / heartbeat 调度闭环
- Twitch 渠道适配层

历史教程和镜像文档已归档到 `docs/archive/`，不作为日常入口。

## 环境配置

依赖统一由 `uv`、`pyproject.toml` 和 `uv.lock` 管理。新增依赖请使用 `uv add <package>`，同步环境请使用 `uv sync`。

```bash
uv sync
```

## 初始化

```bash
uv run ipilot onboard
uv run ipilot status
```

默认配置文件位于 `~/.ipilot/config.json`，默认 workspace 位于 `~/.ipilot/workspace`。

## CLI

单轮非流式对话：

```bash
uv run ipilot agent -m "Reply with exactly: hello"
```

单轮流式输出：

```bash
uv run ipilot agent -m "Tell me a short story" --stream
```

启动 heartbeat，轮询 `workspace/cron/jobs.json` 中的任务：

```bash
uv run ipilot heartbeat --interval-seconds 30
```

## SDK

```python
import asyncio

from ipilot import iPilot


async def main():
    bot = iPilot.from_config()
    response = await bot.run("Reply with exactly: hello", channel="sdk", chat_id="default")
    print(response.content)


asyncio.run(main())
```

流式 SDK：

```python
import asyncio

from ipilot import iPilot


async def main():
    bot = iPilot.from_config()

    def on_delta(delta: str) -> None:
        print(delta, end="", flush=True)

    await bot.run_stream(
        "Write one short paragraph.",
        on_delta=on_delta,
        channel="sdk",
        chat_id="default",
    )
    print()


asyncio.run(main())
```

## HTTP API

启动：

```bash
uv run uvicorn ipilot.api.server:app --reload --port 8900
```

健康检查：

```bash
curl http://127.0.0.1:8900/health
```

最小 chat completions：

```bash
curl http://127.0.0.1:8900/v1/chat/completions ^
  -H "Content-Type: application/json" ^
  -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Reply with exactly: hello\"}]}"
```

## Cron / Heartbeat

最小任务文件位于 `workspace/cron/jobs.json`，任务结构示例：

```json
[
  {
    "id": "cron-demo",
    "prompt": "Reply with exactly: hello",
    "schedule": "*/5 * * * *",
    "next_run_at": "2026-01-01T12:00:00",
    "enabled": true
  }
]
```

heartbeat 会把到期任务作为 `channel="cron"`、`chat_id="<job.id>"` 的输入重新送回统一主链。

## Twitch 渠道

配置方式：配置文件为主，环境变量可覆盖敏感字段。

`config.json` 中的最小结构：

```json
{
  "channels": {
    "twitch": {
      "enabled": true,
      "client_id": "your-client-id",
      "access_token": "your-user-access-token",
      "broadcaster_id": "channel-owner-id",
      "sender_id": "bot-user-id",
      "eventsub_ws_url": "wss://eventsub.wss.twitch.tv/ws",
      "helix_api_base": "https://api.twitch.tv/helix"
    }
  }
}
```

可覆盖的环境变量：

- `IPILOT_TWITCH_ENABLED`
- `IPILOT_TWITCH_CLIENT_ID`
- `IPILOT_TWITCH_ACCESS_TOKEN`
- `IPILOT_TWITCH_BROADCASTER_ID`
- `IPILOT_TWITCH_SENDER_ID`
- `IPILOT_TWITCH_EVENTSUB_WS_URL`
- `IPILOT_TWITCH_HELIX_API_BASE`

启动最小 Twitch 渠道：

```bash
uv run ipilot channel twitch
```

当前范围固定为：

- 只处理 `channel.chat.message`
- 只处理文本消息
- 单频道
- 不做 OAuth refresh

## 测试

直接运行：

```bash
uv run pytest -q
```

当前测试覆盖：

- provider retry / streaming
- agent loop 非流式与流式
- cron / heartbeat 闭环
- Twitch 消息映射
- CLI / API 基本入口
- Twitch 环境变量覆盖

## 许可证

本项目采用 GNU Affero General Public License v3.0 或更高版本（`AGPL-3.0-or-later`）。完整文本见 [`LICENSE`](LICENSE)。
