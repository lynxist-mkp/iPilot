# 第 02 章：模型层迁移到 LangChain

## 本章目标

把“模型怎么初始化、怎么调用”从手写 provider 包装迁到 LangChain。

这一章结束后，你要达成的是：

- 不再让业务代码直接依赖 `OpenAICompatibleProvider`
- 统一通过 LangChain chat model 调用模型
- 继续保留 `api_base`，兼容当前 OpenAI-compatible 后端

## 本章要改哪些文件

- `ipilot/agent/models.py`（新增）
- `ipilot/agent/types.py`（新增）
- `ipilot/agent/runtime_context.py`（新增）
- `ipilot/runtime.py`

这章仍然不动最终的 LangGraph 主循环。

## 1. 先定义新的内部类型

建议你先加 `ipilot/agent/types.py`：

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

再加 `ipilot/agent/runtime_context.py`：

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

## 2. 建一个模型工厂

新增 `ipilot/agent/models.py`：

```python
from langchain_openai import ChatOpenAI

from ipilot.config.schema import Config


def build_chat_model(config: Config):
    provider_name = config.agents.defaults.provider
    provider_config = getattr(config.providers, provider_name)

    return ChatOpenAI(
        model=config.agents.defaults.model,
        api_key=provider_config.api_key,
        base_url=provider_config.api_base,
        temperature=config.agents.defaults.temperature,
    )
```

为什么这里选 `ChatOpenAI`：

- 你当前后端已经是 OpenAI-compatible 风格
- 迁移成本最低
- 后面如果你想进一步泛化，再考虑 `init_chat_model`

## 3. `runtime.py` 先接入模型工厂

这一节只做一件事：把“怎么创建模型”从 `runtime.py` 里抽出来，统一交给 `build_chat_model(config)`。

你现在不要做两件事：

- 不要把 `AgentLoop` 一次性改成 LangChain / LangGraph 版本
- 不要在这一章就删掉 `OpenAICompatibleProvider`

这一章的目标只是让 `runtime.py` 认识新的模型工厂。真正把这个模型对象用进 LangChain agent 的地方，是第 4 章和第 5 章。

### 3.1 `runtime.py` 先加 import

在 `ipilot/runtime.py` 顶部加这一句：

```python
from ipilot.agent.models import build_chat_model
```

### 3.2 `build_agent_loop(...)` 里先拿到模型对象

如果你现在还在保留旧主链，`build_agent_loop` 可以先长这样：

```python
def build_agent_loop(config: Config):
    chat_model = build_chat_model(config)
    ...
```

这里的 `chat_model` 是给后续章节预留的入口。

你可以把它理解成“先把模型创建这件事标准化”，这样后面第 4 章做 `create_agent(...)`、第 5 章做 `StateGraph` 的时候，都会复用同一段初始化逻辑。

### 3.3 这一节你实际要敲的代码

如果你只想照着教程做，按下面两步来：

1. 新建 [`ipilot/agent/models.py`](../../ipilot/agent/models.py)，写好 `build_chat_model(config)`
2. 在 [`ipilot/runtime.py`](../../ipilot/runtime.py) 里补上 `from ipilot.agent.models import build_chat_model`

然后先不要继续往下改主循环，等第 4 章再让这个模型对象进入 LangChain agent。

## 4. 为什么不能继续保留 `LLMProvider`

问题不是“代码坏”，而是抽象层级不对。

一旦进 LangChain / LangGraph：

- 模型调用已经有统一接口
- streaming 已经有现成机制
- tool call schema 已经有标准约定
- middleware 也围绕 LangChain model 工作

如果你继续让主链依赖 `LLMProvider`，后面会发生两层重复抽象。

## 5. 最小单测建议

这一章最值得补的，是一个纯模型初始化测试：

```python
from ipilot.agent.models import build_chat_model
from ipilot.config.schema import Config


def test_build_chat_model_uses_current_provider_config():
    config = Config(
        agents={"defaults": {"provider": "stepfun", "model": "step-3.5-flash", "temperature": 0.0}},
        providers={"stepfun": {"api_key": "demo-key", "api_base": "https://example.invalid/v1"}},
    )

    model = build_chat_model(config)

    assert model.model_name == "step-3.5-flash"
```

## 6. 本章常见坑

### 坑 1：把 `api_base` 写成 `base_url`

`ChatOpenAI` 一般用 `base_url`。要在工厂里做映射。

### 坑 2：想一次支持所有 provider

别急。当前仓库只有一个默认 provider，先把这一条跑顺。

### 坑 3：现在就把所有旧 provider 文件删了

还是不要。等第 5-6 章完全切过去，再做清理。

## 7. 本章验证

至少跑下面两步：

```bash
uv run python -c "from ipilot.agent.models import build_chat_model; print('ok')"
uv run pytest -q tests/test_package_exports.py tests/test_config_loader.py
```

通过标准：

- LangChain model 工厂能 import
- 当前配置加载不受影响
- 你已经不需要再把“模型调用协议”绑死在 `LLMProvider` 上
