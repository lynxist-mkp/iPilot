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

## 0. 先认清当前状态

你现在不是从零开始，而是在一份“已经半迁移”的代码上继续往前推。

当前最关键的现实是：

- `runtime.py` 已经开始走 `build_agent_loop(...)`
- `loop.py` 已经能拿到 `graph`，但还残留旧链路方法
- `graph_runtime.py` 已经有 `StateGraph` 骨架，但还没把高级能力全接完

所以这一章不要追求“把所有旧文件一次删光”，而是先做两件事：

1. 让主入口稳定跑在 graph 上
2. 把旧链路从主路径里挪出去

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

这一章里最关键的判断标准很简单：

- 如果你还在 `AgentLoop` 里拼接 tool call 消息，说明还没迁完
- 如果你还在 `AgentLoop` 里自己保存 session，说明还没迁完
- 如果你还在 `AgentLoop` 里 while-loop 执行工具，说明还没迁完

主循环迁移完成后，`loop.py` 应该像适配器，不像业务实现。

### 1.1 你现在改 `loop.py` 的顺序

如果你是边看边改，建议按这个顺序来：

1. 先把 `process_direct(...)` 调通
2. 再把 `process_direct_stream(...)` 改成兼容版
3. 最后再考虑删掉旧的 `_execute_tool_round(...)`、`_save_turn(...)`、`SessionManager` 相关路径

不要一上来就同时改流式、工具循环、会话持久化，那样最容易改乱。

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

### 2.1 `middleware` 这版先怎么处理

如果你已经在第 4 章用过 `create_agent(...)`，会自然想到 middleware。

但这一章是“先把主链切过去”，不是“同时把所有横切逻辑都整理完”。所以第一版最稳的做法是：

1. 先保留 `middleware` 参数，作为未来扩展位
2. 先不要把 prompt 注入和 graph 节点编排一起做

等 `AgentLoop` 和 checkpointer 跑顺以后，再考虑把 system prompt 进一步抽成 graph 前置节点。

也就是说，这一版的教程里，`middleware` 先是“保留接口”，不是“必须已经接通的功能”。

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

    async def process_direct(
        self,
        message: str,
        session_key: str,
        channel: str | None = None,
        chat_id: str | None = None,
    ):
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

    async def process_direct_stream(
        self,
        message: str,
        session_key: str,
        on_stream=None,
        channel: str | None = None,
        chat_id: str | None = None,
    ):
        result = await self.process_direct(
            message,
            session_key,
            channel=channel,
            chat_id=chat_id,
        )

        if on_stream is not None and result.content:
            maybe = on_stream(result.content)
            if hasattr(maybe, "__await__"):
                await maybe

        return result
```

这段代码后面还会继续打磨，但三个结构性变化已经定了：

- `SessionManager` 不再是主存储
- `ContextBuilder` 不再负责消息拼接
- `AgentLoop` 不再自己执行工具循环

第一轮迁移里，这个 `process_direct_stream(...)` 允许先是“兼容版”，也就是：

- 先保证 CLI 的 `--stream` 不炸
- 先保证外层仍然能拿到 `.content`
- 真正的 token 级流式输出，放到后续再细化

如果你现在只想把教程里的“最小闭环”敲通，`process_direct_stream(...)` 就先别追求真 `astream(...)`。先确保它不破坏外层行为，再慢慢升级成真正的流式实现。

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


def build_agent_loop(config: Config) -> AgentLoop:
    model = build_chat_model(config)
    tools = build_langchain_tools(config.workspace_path)
    graph = build_agent_graph(
        model=model,
        tools=tools,
        middleware=[build_system_prompt],
        sqlite_path=str(config.workspace_path / "checkpoints.sqlite3"),
    )
    context_factory = build_runtime_context_factory(config)
    return AgentLoop(graph=graph, context_factory=context_factory)
```

这一段最好按这个顺序敲：

1. 先把 `build_runtime_context_factory(...)` 写出来
2. 再写 `build_agent_loop(...)`
3. 再让 `iPilot.from_config()` 继续调用 `build_agent_loop(...)`
4. 最后跑测试确认 `run(...)` 还在

如果你卡住，先确认一个原则：

- `build_agent_loop(...)` 是主装配入口
- `build_experiment_agent(...)` 只是试验入口
- `build_tool_registry(...)` 和旧 provider 链路不要再被主入口调用

## 6. `MessagesState` 为什么够用

当前仓库第一轮迁移不需要自定义复杂状态对象。

原因：

- 你的核心任务就是“围绕消息跑 agent”
- 历史消息本来就是主状态
- 工具调用回写也天然围绕消息流

所以第一版推荐：

- 主状态：`MessagesState`
- 额外 metadata：放 runtime context，而不是塞进 graph state

如果以后你想扩状态，比如审批标记、重试计数、外部任务 id，再考虑自定义 state。第一版别提前上复杂度。

### 6.1 这章和第 7 章怎么分工

第 5 章只负责把“普通消息流”跑顺。

- 第 5 章解决：消息进来，图跑起来，工具能用，结果能出来
- 第 7 章解决：图跑到一半要停、要等人确认、要 resume

不要在第 5 章里硬塞 `interrupt` 语义。那会把两章的边界搅乱。

## 7. streaming 怎么理解

当前仓库的 streaming 是 provider 层自己发 delta。

迁到 LangGraph 后，你要换一个视角：

- streaming 不是 provider 私活
- streaming 是 graph runtime 的一种输出模式

所以未来正确结构是：

- `process_direct(...)` -> `graph.ainvoke(...)`
- `process_direct_stream(...)` -> `graph.astream(...)`

如果你这一轮还没把真正的 `astream` 打通，就先保留兼容版 `process_direct_stream(...)`，等主链稳定后再替换成更细的增量事件。

### 7.1 当前代码和教程的对应关系

如果你现在打开 `graph_runtime.py`，会发现 `confirm_dangerous_action(...)` 还只是一个示意函数。

这不是 bug，而是说明：

- 第 5 章里的图骨架已经可以先跑
- 第 7 章的审批流程还要单独接线

所以不要把 `confirm_dangerous_action(...)` 当成已经可用的功能；它还只是高级篇里的示例。

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
3. 返回值仍然能从 `.content` 直接读取最终结果

再跑回归：

```bash
uv run pytest -q tests/test_agent_loop.py
```

通过标准：

- `AgentLoop` 已变成 graph facade
- 工具循环不再手写
- 会话状态主来源变成 LangGraph checkpointer
- 外层调用不需要知道图内部细节
