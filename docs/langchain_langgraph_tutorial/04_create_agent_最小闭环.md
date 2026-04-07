# 第 04 章：`create_agent(...)` 最小闭环

## 本章目标

先不要急着上 `StateGraph`。这一章的目标是用 LangChain 的高层 agent 入口，快速证明三件事：

1. 新模型对象能和新工具对象协作
2. middleware 能工作
3. `thread_id` / checkpointer 这些概念你已经看得懂

这是“练手章”，不是最终生产主链。

## 本章要改哪些文件

- `ipilot/agent/middleware.py`（新增）
- `ipilot/runtime.py`
- 可选：`tests/` 下补一个最小 smoke test

## 1. 先写 middleware

新增 `ipilot/agent/middleware.py`：

```python
from langchain.agents.middleware import dynamic_prompt


@dynamic_prompt
def build_system_prompt(request) -> str:
    ctx = request.runtime.context
    parts = [
        "You are iPilot.",
        f"Workspace: {ctx.workspace_path}",
        f"Provider: {ctx.provider}",
        f"Model: {ctx.model}",
    ]
    if ctx.channel:
        parts.append(f"Channel: {ctx.channel}")
    if ctx.chat_id:
        parts.append(f"Chat ID: {ctx.chat_id}")
    return "\n".join(parts)
```

这里最重要的不是 prompt 本身，而是你要意识到一件事：

运行时上下文已经不需要再手工塞进 user message 了。

## 2. 先做一个“最小 agent spike”

在 `runtime.py` 里先加一个实验性构造函数：

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from ipilot.agent.middleware import build_system_prompt
from ipilot.agent.models import build_chat_model
from ipilot.agent.langchain_tools import build_langchain_tools


def build_experimental_agent(config: Config):
    model = build_chat_model(config)
    tools = build_langchain_tools(config.workspace_path)
    checkpointer = InMemorySaver()

    return create_agent(
        model=model,
        tools=tools,
        middleware=[build_system_prompt],
        checkpointer=checkpointer,
    )
```

## 3. 先手动调用一次

建议你写一个临时脚本或 REPL 调用，感受调用形态：

```python
from ipilot.agent.runtime_context import AgentRuntimeContext
from ipilot.runtime import build_experimental_agent
from ipilot.config.loader import load_config

config = load_config()
agent = build_experimental_agent(config)
context = AgentRuntimeContext(
    session_key="sdk:default",
    channel="sdk",
    chat_id="default",
    workspace_path=config.workspace_path,
    provider=config.agents.defaults.provider,
    model=config.agents.defaults.model,
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "Reply with exactly: hello"}]},
    config={"configurable": {"thread_id": context.session_key}},
    context=context,
)
print(result)
```

你在这里要建立两个关键映射：

- `session_key -> thread_id`
- `context=AgentRuntimeContext(...)`

## 4. 为什么这一章不是最终架构

因为 `create_agent(...)` 虽然很适合上手，但你这个仓库最后要的是：

- 更明确的节点边界
- 更可控的主循环
- 更容易接入 interrupt/resume
- 更清晰的 streaming / persistence 控制

这些能力都更适合在第 5 章用 LangGraph 明确表达。

## 5. 结构化输出先知道，不强上

这章你可以顺便知道 `create_agent(...)` 能带 `response_format`，但不建议在当前仓库第一轮迁移时就强上。

原因：

- 你当前对外接口主要还是 `.content`
- 结构化输出会额外引入 schema 设计
- 这会分散对主链迁移的注意力

## 6. 本章常见坑

### 坑 1：把 `create_agent(...)` 当成最终生产形态

不是。它是第 4 章的桥梁。

### 坑 2：继续让 `ContextBuilder` 生成 system prompt

不要。system prompt 现在应该转向 middleware。

### 坑 3：误以为 `checkpointer` 只属于 LangGraph，不属于 LangChain agent

LangChain agent 底座就是 LangGraph，所以你在这里先看见它是正常的。

## 7. 本章验证

最小验证脚本能跑通即可。再加一个 smoke test 更稳：

```bash
uv run pytest -q tests/test_package_exports.py
```

本章通过标准：

- 你已经用 `create_agent(...)` 跑过一次
- 你已经理解 `middleware + tools + checkpointer + thread_id`
- 你已经准备好进入真正的 LangGraph 重构
