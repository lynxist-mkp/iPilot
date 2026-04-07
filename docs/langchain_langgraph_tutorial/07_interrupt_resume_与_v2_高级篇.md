# 第 07 章：`interrupt` / `resume` 与 `version="v2"` 高级篇

## 本章目标

前 6 章已经能让 `iPilot` 跑起来了。

这一章处理的是 LangGraph 真正拉开差距的部分：

- interrupt / resume
- 持久化暂停点
- `version="v2"` 结果形态

这不是基础迁移必需项，但它是你选择 LangGraph 而不是只停在 `create_agent(...)` 的核心理由之一。

## 本章要改哪些文件

- `ipilot/agent/graph_runtime.py`
- `ipilot/agent/types.py`
- 新增或补充测试

## 1. 先理解 interrupt 到底解决什么问题

它真正解决的是：

- 图执行到某一步时，需要人确认
- 这个暂停状态必须可恢复
- 恢复后不能丢线程上下文

对 `iPilot` 这种 agent 框架来说，典型场景包括：

- 高风险 shell 命令确认
- 写文件前人工审批
- 外部渠道敏感消息发送确认

## 2. 先写一个最小 interrupt 节点

在 `ipilot/agent/graph_runtime.py` 里先加一个实验节点：

```python
from langgraph.types import interrupt


def confirm_dangerous_action(state, runtime):
    last_message = state["messages"][-1]
    text = getattr(last_message, "content", "") or ""
    if "rm -rf" not in text:
        return {}

    approval = interrupt(
        {
            "kind": "approval",
            "question": "检测到高风险命令，是否继续？",
            "session_key": runtime.context.session_key,
        }
    )
    return {"approval": approval}
```

这里要记住官方约束：

- `interrupt(...)` 的调用顺序必须稳定
- 传入内容必须可序列化
- `interrupt` 前面的副作用必须幂等

### 2.1 这个节点应该放在哪里

第一版最稳的放置点，是“模型已经表达出高风险意图，但工具还没真的执行”。

这样你可以把审批点放在：

1. 调模型之后
2. 执行工具之前

不要把审批逻辑塞进工具实现内部。那样会把副作用和审批强耦合，恢复时会很难收拾。

### 2.2 让它真正生效，需要接进 graph

只写 `confirm_dangerous_action(...)` 还不够，它必须挂到 `build_agent_graph(...)` 的路径上。

第 7 章最小接法可以是这样：

```python
def build_agent_graph(*, model, tools, middleware, sqlite_path):
    tool_node = ToolNode(tools)

    def call_model(state: MessagesState, runtime):
        response = model.invoke(state["messages"], context=runtime.context)
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_node("confirm", confirm_dangerous_action)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "call_model")
    builder.add_edge("call_model", "confirm")
    builder.add_conditional_edges("confirm", tools_condition, {"tools": "tools", "__end__": END})
    builder.add_edge("tools", "call_model")

    checkpointer = SqliteSaver.from_conn_string(sqlite_path)
    return builder.compile(checkpointer=checkpointer)
```

这段代码的意思是：

1. 模型先产出一次回复
2. `confirm_dangerous_action(...)` 有机会在工具执行前打断
3. 如果没有被打断，再继续走 `tools_condition`

注意这里的 `confirm_dangerous_action(...)` 是一个“拦截点”，不是新的业务分支。

如果你自己代码里还写着 `sessino_key`，这里要一并改成 `session_key`。

## 3. 恢复时怎么调用

恢复不是重新开线程，而是继续同一个 `thread_id`。

伪代码形态是：

```python
from langgraph.types import Command

result = await graph.ainvoke(
    Command(resume={"approved": True}),
    config={"configurable": {"thread_id": session_key}},
    context=context,
    version="v2",
)
```

这里要抓住两个关键词：

- `resume`
- 同一个 `thread_id`

如果你想把恢复写得更清晰，可以显式先构造一个 `resume_payload`：

```python
resume_payload = Command(resume={"approved": True})
result = await graph.ainvoke(
    resume_payload,
    config={"configurable": {"thread_id": session_key}},
    context=context,
    version="v2",
)
```

如果你恢复时换了线程，那就不是恢复，是重新开了一次执行。

## 4. 为什么这里推荐 `version="v2"`

因为你不该再教自己未来会淘汰的访问方式。

在低层 LangGraph 示例里，推荐你统一写：

```python
payload = Command(resume={"approved": True})
result = await graph.ainvoke(
    payload,
    config={"configurable": {"thread_id": session_key}},
    context=context,
    version="v2",
)

value = result.value
interrupts = result.interrupts
```

这样你的教程从一开始就把“结果值”和“中断信息”区分开。

如果你当前实现还没完整切到 `value` / `interrupts` 这种目标形态，也没关系。教程里先统一概念，但要明确标注：这就是后面会用到的目标形态。

## 5. `AgentRunResult` 怎么扩一下

这时候 `ipilot/agent/types.py` 的 `AgentRunResult` 就该把 `interrupts` 真正用起来：

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

当 graph 因 interrupt 暂停时：

- `content` 可能为空
- `interrupts` 必须能带出暂停原因

一个比较实用的约定是：

- `content=None` 表示当前轮没有最终自然语言结果
- `interrupts=[...]` 表示需要外部恢复
- `finish_reason="interrupt"` 可以作为额外标记

这样 CLI / API 层就能很简单地判断：

1. 正常完成，打印 `.content`
2. 被打断，展示审批信息
3. 恢复后继续走同一个 `session_key`

## 6. 一个适合 `iPilot` 的接法

我建议你把 interrupt 能力先限制在“内部高级 API”里，不要马上暴露到所有入口。

第一版最稳的策略是：

- `iPilot.run(...)` 保持基础同步结果
- 新增一个内部可选路径，专门处理 `interrupts`
- 等 CLI / API 想支持审批流时，再设计对外交互协议

你可以先把内部路径设计成两个动作：

1. `run(...)` 返回 `AgentRunResult`
2. 如果结果里带 `interrupts`，上层决定是否调用 `resume(...)`

这样不会把“审批对话”硬塞进普通聊天入口。

## 7. 本章常见坑

### 坑 1：在 `interrupt(...)` 前先做不可逆副作用

例如先写文件、先发消息、先删目录，然后再问用户是否继续。这是错的。

### 坑 2：恢复时换 `thread_id`

这会让 LangGraph 找不到原来的暂停点。

### 坑 3：在教程里继续教旧式结果读取

既然你已经写高级篇，就直接上 `version="v2"`。

## 8. 本章验证

这一章必须补一个真正的 interrupt / resume 测试。

最少要覆盖下面流程：

1. 用 `session_key = "sdk:interrupt-demo"` 启动一次执行
2. 图在 interrupt 点暂停
3. 记录返回的 `interrupts`
4. 用同一个 `thread_id` 执行 resume
5. 图继续跑完
6. 恢复后的结果还能看到前面的线程上下文

测试最好拆成两个断言阶段：

1. 先确认第一次运行真的返回了 `interrupts`
2. 再确认同一个 `thread_id` resume 后能拿到最终内容

建议测试名直接写清楚，例如：

```python
async def test_langgraph_interrupt_can_resume_on_same_thread_id():
    ...
```

再配合一轮回归：

```bash
uv run pytest -q tests/test_agent_loop.py
```

通过标准：

- interrupt 能触发
- pause 状态能落盘
- resume 使用同一个 `thread_id`
- 恢复后状态连续，没有丢上下文
- `version="v2"` 下你能清楚地区分结果值和中断信息
