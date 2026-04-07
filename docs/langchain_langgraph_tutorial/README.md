# iPilot LangChain / LangGraph 改造教程

这套教程是给当前 `iPilot` 仓库准备的“手把手施工说明”。

- 现有研究文档保留在 [`../langchain_langgraph.md`](../langchain_langgraph.md)
- 本目录只负责“怎么改”
- 默认读者：知道 Python，但对 LangChain / LangGraph 还不熟
- 默认目标：你一边敲，一边把当前仓库逐步迁到 LangChain + LangGraph

## 1. 先看结论

这次不是“全面推倒重来”，而是把现有 `iPilot` 的主链逐层替换掉：

| 当前实现 | 目标实现 | 为什么 |
| --- | --- | --- |
| `OpenAICompatibleProvider` | `ChatOpenAI` / `init_chat_model` | 不再手写 provider 包装层，直接站到 LangChain 模型抽象上 |
| `ToolRegistry + Tool` | `@tool` / `StructuredTool` / `ToolRuntime` | 工具 schema、调用、回写都交给框架 |
| `SessionManager` | LangGraph checkpointer + `thread_id` | 会话状态变成图运行时的一部分 |
| `ContextBuilder` | middleware + runtime context | 不再把运行时上下文硬塞进 user message |
| `AgentLoop` | 编译后的 `StateGraph` + 薄封装 facade | 把手写 while-loop 替换成可持久化的图执行 |

这套教程固定采用“混合架构”：

- LangChain 负责：模型初始化、工具定义、middleware、结构化输出、runtime context
- LangGraph 负责：状态图、checkpoint、thread memory、streaming、interrupt/resume

## 2. 教程目录

按顺序读，不要跳章：

1. [`01_依赖与版本基线.md`](./01_%E4%BE%9D%E8%B5%96%E4%B8%8E%E7%89%88%E6%9C%AC%E5%9F%BA%E7%BA%BF.md)
2. [`02_模型层迁移到_LangChain.md`](./02_%E6%A8%A1%E5%9E%8B%E5%B1%82%E8%BF%81%E7%A7%BB%E5%88%B0_LangChain.md)
3. [`03_工具层迁移到_LangChain_Tools.md`](./03_%E5%B7%A5%E5%85%B7%E5%B1%82%E8%BF%81%E7%A7%BB%E5%88%B0_LangChain_Tools.md)
4. [`04_create_agent_最小闭环.md`](./04_create_agent_%E6%9C%80%E5%B0%8F%E9%97%AD%E7%8E%AF.md)
5. [`05_用_LangGraph_重写_AgentLoop.md`](./05_%E7%94%A8_LangGraph_%E9%87%8D%E5%86%99_AgentLoop.md)
6. [`06_接回_iPilot_外层入口.md`](./06_%E6%8E%A5%E5%9B%9E_iPilot_%E5%A4%96%E5%B1%82%E5%85%A5%E5%8F%A3.md)
7. [`07_interrupt_resume_与_v2_高级篇.md`](./07_interrupt_resume_%E4%B8%8E_v2_%E9%AB%98%E7%BA%A7%E7%AF%87.md)

## 3. 版本基线

本教程固定用下面这一组版本，不追“最新”，追“可复现”：

| 包 | 固定版本 | 说明 |
| --- | --- | --- |
| `langchain` | `1.2.15` | 2026-04-03 发布，Python 要求 `>=3.10` |
| `langgraph` | `1.1.6` | 2026-04-03 发布 |
| `langchain-openai` | `1.1.8` | 教程固定值，避免边写边撞 API 漂移 |
| `langgraph-checkpoint` | `4.0.1` | checkpoint 抽象 |
| `langgraph-checkpoint-sqlite` | `3.0.3` | 本地 SQLite 持久化 |

当前仓库 [`../pyproject.toml`](../pyproject.toml) 已经是 Python `>=3.11`，满足 LangChain / LangGraph 的 Python `>=3.10` 要求。

## 4. 教程里的目标文件布局

本教程默认你最后会把 `ipilot/agent/` 逐步整理成下面这组文件：

```text
ipilot/
  agent/
    loop.py
    types.py
    runtime_context.py
    models.py
    middleware.py
    langchain_tools.py
    graph_runtime.py
```

其中职责固定如下：

- `types.py`
  统一内部结果对象，例如 `AgentRunResult`
- `runtime_context.py`
  定义运行时上下文对象，例如 `AgentRuntimeContext`
- `models.py`
  负责初始化 `ChatOpenAI` 或 `init_chat_model`
- `middleware.py`
  动态 system prompt、运行时上下文注入、日志/限流/重试等横切逻辑
- `langchain_tools.py`
  从现有文件系统 / shell 工具迁到 LangChain tool
- `graph_runtime.py`
  定义 `MessagesState`、节点、边、checkpointer、graph 编译
- `loop.py`
  只保留对 graph 的薄封装，继续给 `iPilot.run(...)` 使用

## 5. 两个核心类型先统一

### 5.1 运行时上下文

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AgentRuntimeContext:
    session_key: str
    channel: str | None
    chat_id: str | None
    workspace_path: Path
    provider: str
    model: str
```

要点：

- `session_key` 直接映射到 LangGraph 的 `thread_id`
- `channel/chat_id` 不再塞进用户消息正文
- `workspace_path/provider/model` 作为 middleware 和工具运行时的稳定输入

### 5.2 统一结果对象

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentRunResult:
    content: str | None
    messages: list[Any] = field(default_factory=list)
    finish_reason: str = "stop"
    interrupts: list[Any] = field(default_factory=list)
```

要点：

- 这是新的内部主结果类型
- 它替代当前 provider 形态的 `LLMResponse`
- 对外仍然保留 `.content`

## 6. 你应该怎么跟着敲

建议严格按下面节奏走：

1. 先读每章开头的“本章目标”
2. 只改本章列出来的文件
3. 把本章末尾的验证命令跑过
4. 通过以后再进下一章

## 7. 安全检查点

每章都必须做到“能停下来”。如果时间不够，至少停在这些检查点：

- 第 1 章结束：依赖和配置层准备好
- 第 3 章结束：LangChain tools 能独立工作
- 第 4 章结束：最小 `create_agent(...)` 能跑通
- 第 5 章结束：LangGraph 主链替掉手写 `AgentLoop`
- 第 6 章结束：CLI / API / heartbeat / Twitch 接回去
- 第 7 章结束：interrupt / resume / `version="v2"` 验证完成

## 8. 回归测试锚点

教程里会反复引用这些现有测试：

- [`../../tests/test_agent_loop.py`](../../tests/test_agent_loop.py)
- [`../../tests/test_cli_commands.py`](../../tests/test_cli_commands.py)
- [`../../tests/test_api_server.py`](../../tests/test_api_server.py)
- [`../../tests/test_twitch_channel.py`](../../tests/test_twitch_channel.py)

另外，迁移完成后还应补两类新测试：

- checkpoint 持久化测试
- interrupt / resume 测试

## 9. 官方参考

- LangChain Agents: <https://docs.langchain.com/oss/python/langchain/agents>
- LangChain Custom Middleware: <https://docs.langchain.com/oss/python/langchain/middleware/custom>
- LangGraph Quickstart: <https://docs.langchain.com/oss/python/langgraph/quickstart>
- LangGraph Persistence: <https://docs.langchain.com/oss/python/langgraph/persistence>
- LangGraph Memory: <https://docs.langchain.com/oss/python/langgraph/add-memory>
- LangGraph Interrupts: <https://docs.langchain.com/oss/python/langgraph/interrupts>
- PyPI `langchain==1.2.15`: <https://pypi.org/project/langchain/>
- PyPI `langgraph==1.1.6`: <https://pypi.org/project/langgraph/>
- PyPI `langchain-openai`: <https://pypi.org/project/langchain-openai/>
- PyPI `langgraph-checkpoint==4.0.1`: <https://pypi.org/project/langgraph-checkpoint/>
- PyPI `langgraph-checkpoint-sqlite==3.0.3`: <https://pypi.org/project/langgraph-checkpoint-sqlite/>

读完这里，进入第 1 章。
