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

## 3. 恢复时怎么调用

恢复不是重新开线程，而是继续同一个 `thread_id`。

伪代码形态是：

```python
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

如果你恢复时换了线程，那就不是恢复，是重新开了一次执行。

## 4. 为什么这里推荐 `version="v2"`

因为你不该再教自己未来会淘汰的访问方式。

在低层 LangGraph 示例里，推荐你统一写：

```python
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

## 6. 一个适合 `iPilot` 的接法

我建议你把 interrupt 能力先限制在“内部高级 API”里，不要马上暴露到所有入口。

第一版最稳的策略是：

- `iPilot.run(...)` 保持基础同步结果
- 新增一个内部可选路径，专门处理 `interrupts`
- 等 CLI / API 想支持审批流时，再设计对外交互协议

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
