# 第 05 章：用 LangGraph 重写 `AgentLoop`

## 本章目标

这一章才是真正的主战场。

你要把当前 `ipilot/agent/loop.py` 里手写的：

- `process_direct(...)`
- `process_direct_stream(...)`
- `_execute_tool_round(...)`

替换成一个编译后的 LangGraph runtime，再保留一个很薄的 facade 给外层入口继续调用。

## 本章要改哪些文件

- `ipilot/agent/graph_runtime.py`（新增）
- `ipilot/agent/loop.py`
- `ipilot/runtime.py`

## 1. 先明确“新 loop 不该再做什么”

当前 `AgentLoop` 做了太多事情：

- 读 session history
- 组 messages
- 调 provider
- 解析 tool calls
- 执行工具
- 继续 while-loop
- 保存 session

迁移后，`loop.py` 应该只保留两类职责：

1. 把外部调用转换成 graph invoke / stream 调用
2. 把 graph 输出整理成 `AgentRunResult`

## 2. 先写 graph builder

新增 `ipilot/agent/graph_runtime.py`：

```python
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.sqlite import SqliteSaver


def build_agent_graph(*, model, tools, middleware, sqlite_path):
    tool_node = ToolNode(tools)

    def call_model(state: MessagesState, runtime):
        response = model.invoke(state["messages"], context=runtime.context)
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "call_model")
    builder.add_conditional_edges("call_model", tools_condition, {"tools": "tools", "__end__": END})
    builder.add_edge("tools", "call_model")

    checkpointer = SqliteSaver.from_conn_string(sqlite_path)
    return builder.compile(checkpointer=checkpointer)
```

这一版的关键点只有三个：

- 状态采用 `MessagesState`
- 工具执行交给 `ToolNode`
- 持久化交给 SQLite checkpointer

## 3. 为什么现在可以退休 `_execute_tool_round(...)`

因为 `ToolNode + tools_condition + graph edge` 已经把这个循环表达出来了。

你之前手写的 while-loop 本质上是在做：

1. 调模型
2. 看有没有工具调用
3. 如果有就执行工具
4. 把结果回写
5. 再调模型

这正是图最擅长表达的东西。

## 4. `loop.py` 改成薄封装

新的 `ipilot/agent/loop.py` 建议长这样：

```python
from ipilot.agent.types import AgentRunResult


class AgentLoop:
    def __init__(self, graph, context_factory):
        self.graph = graph
        self.context_factory = context_factory

    async def process_direct(self, message: str, session_key: str, channel: str | None = None, chat_id: str | None = None):
        context = self.context_factory(session_key=session_key, channel=channel, chat_id=chat_id)
        result = await self.graph.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            config={"configurable": {"thread_id": session_key}},
            context=context,
        )
        messages = result["messages"]
        last = messages[-1]
        return AgentRunResult(
            content=getattr(last, "content", None),
            messages=messages,
            finish_reason="stop",
        )
```

这段代码后面还会继续打磨，但三个结构性变化已经定了：

- `SessionManager` 不再是主存储
- `ContextBuilder` 不再负责消息拼接
- `AgentLoop` 不再自己执行工具循环

## 5. `runtime.py` 最终装配形态

这时候 `ipilot/runtime.py` 就应该真正负责装 graph：

```python
from ipilot.agent.graph_runtime import build_agent_graph
from ipilot.agent.langchain_tools import build_langchain_tools
from ipilot.agent.loop import AgentLoop
from ipilot.agent.middleware import build_system_prompt
from ipilot.agent.models import build_chat_model
from ipilot.agent.runtime_context import AgentRuntimeContext


def build_runtime_context_factory(config: Config):
    def factory(*, session_key: str, channel: str | None, chat_id: str | None):
        return AgentRuntimeContext(
            session_key=session_key,
            channel=channel,
            chat_id=chat_id,
            workspace_path=config.workspace_path,
            provider=config.agents.defaults.provider,
            model=config.agents.defaults.model,
        )
    return factory
```

## 6. `MessagesState` 为什么够用

当前仓库第一轮迁移不需要自定义复杂状态对象。

原因：

- 你的核心任务就是“围绕消息跑 agent”
- 历史消息本来就是主状态
- 工具调用回写也天然围绕消息流

所以第一版推荐：

- 主状态：`MessagesState`
- 额外 metadata：放 runtime context，而不是塞进 graph state

## 7. streaming 怎么理解

当前仓库的 streaming 是 provider 层自己发 delta。

迁到 LangGraph 后，你要换一个视角：

- streaming 不是 provider 私活
- streaming 是 graph runtime 的一种输出模式

所以未来正确结构是：

- `process_direct(...)` -> `graph.ainvoke(...)`
- `process_direct_stream(...)` -> `graph.astream(...)`

## 8. 本章常见坑

### 坑 1：一边保留 `SessionManager`，一边上 SQLite checkpointer

这会让你有两套状态源。主路径只能有一个真相来源。

### 坑 2：继续把 runtime context 写进 user content

不要。它应该走 `context=...`。

### 坑 3：先自己重写工具调用循环，再塞进 graph

没有必要。`ToolNode` 存在就是为了不让你再做这件事。

## 9. 本章验证

至少需要有一个新测试验证“同一个 `thread_id` 能保留上下文”。

推荐目标测试逻辑：

1. 用同一个 `session_key` 调两次 `process_direct(...)`
2. 第二次运行时能看到第一轮消息已经在图状态里

再跑回归：

```bash
uv run pytest -q tests/test_agent_loop.py
```

通过标准：

- `AgentLoop` 已变成 graph facade
- 工具循环不再手写
- 会话状态主来源变成 LangGraph checkpointer
