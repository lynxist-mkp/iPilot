# 第 03 章：工具层迁移到 LangChain Tools

## 本章目标

把当前 `ToolRegistry + Tool` 体系迁到 LangChain 的工具体系，同时保留现有文件系统 / shell 能力。

这一章结束后，你要得到：

- 一组 LangChain tool
- 明确知道什么时候返回普通字符串
- 明确什么时候需要 `ToolRuntime`
- `ToolRegistry` 不再是主路径核心

## 本章要改哪些文件

- `ipilot/agent/langchain_tools.py`（新增）
- `ipilot/runtime.py`

参考旧实现：

- `ipilot/agent/tools/base.py`
- `ipilot/agent/tools/filesystem.py`
- `ipilot/agent/tools/shell.py`

## 1. 先决定保留哪些工具

先只迁这 5 个：

- `read_file`
- `list_dir`
- `write_file`
- `edit_file`
- `exec`

不要一开始加新工具。迁移期最忌讳“顺手多做一点”。

## 2. 把旧工具改写成 `@tool`

新增 `ipilot/agent/langchain_tools.py`：

```python
from pathlib import Path

from langchain.tools import tool


def build_langchain_tools(workspace: Path):
    @tool
    def read_file(path: str) -> str:
        """Read a UTF-8 text file from the workspace."""
        return (workspace / path).read_text(encoding="utf-8")

    @tool
    def list_dir(path: str = ".") -> list[str]:
        """List entries in a workspace directory."""
        return sorted(item.name for item in (workspace / path).iterdir())

    @tool
    def write_file(path: str, content: str) -> str:
        """Write UTF-8 text to a workspace file."""
        full_path = workspace / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"Wrote to {full_path}"

    @tool
    def edit_file(path: str, old_text: str, new_text: str) -> str:
        """Apply a single replace operation to a workspace file."""
        full_path = workspace / path
        content = full_path.read_text(encoding="utf-8")
        updated = content.replace(old_text, new_text, 1)
        full_path.write_text(updated, encoding="utf-8")
        return f"Edited {full_path}"

    @tool
    def exec(command: str) -> str:
        """Execute a shell command in the workspace and return merged output."""
        import subprocess

        completed = subprocess.run(
            command,
            cwd=workspace,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        return (completed.stdout or "") + (completed.stderr or "")

    return [read_file, list_dir, write_file, edit_file, exec]
```

这里的 `subprocess` 是 Python 标准库，不需要执行 `uv add subprocess`。直接 `import subprocess` 就可以。

这里先写成同步函数是为了让第一版工具更直观。后面如果某个工具明显 I/O 重，可以再迁到 async。

## 3. 什么时候返回普通值就够了

这套仓库的第一版工具，大多数场景返回普通 Python 值就够了：

- 文件内容：`str`
- 目录列表：`list[str]`
- 命令输出：`str`

所以第一版建议：

- `read_file` 返回 `str`
- `list_dir` 返回 `list[str]`
- `write_file/edit_file/exec` 返回 `str`

## 4. 什么情况下才需要 `ToolMessage`

这一版教程里，不要求你手工构造 `ToolMessage` 作为常规返回值。

原因：

- 在 LangChain agent / LangGraph `ToolNode` 路径里，框架会处理工具调用消息回写
- 你当前最需要的是“把旧工具迁进去”，不是自己重新发明消息协议

只有当你在图节点里手工拼接工具调用往返消息时，才会主动处理 `ToolMessage`。

## 5. 什么情况下需要 `ToolRuntime`

`ToolRuntime` 用在“工具执行时需要读取运行时上下文”的场景。

这套仓库最典型的两个用途是：

1. 根据 `channel/chat_id` 调整工具行为
2. 读取 `workspace_path`、`provider`、`model` 之类的运行时信息

比如你以后想写一个“只允许在指定工作目录内执行”的工具，就可以让工具拿到 runtime context：

```python
from langchain.tools import tool, ToolRuntime


@tool
def read_file(path: str, runtime: ToolRuntime) -> str:
    ctx = runtime.context
    workspace = ctx.workspace_path
    return (workspace / path).read_text(encoding="utf-8")
```

第一版是否要马上用 `ToolRuntime`？

我的建议是：

- 第 3 章可以先不用
- 但文档设计必须从一开始就兼容它
- 第 5 章切到 LangGraph 主链时，再把 runtime context 真的接进来

## 6. `runtime.py` 的工具装配点

把 `ipilot/runtime.py` 的工具构造逻辑也改成工厂形式：

```python
from ipilot.agent.langchain_tools import build_langchain_tools


def build_toolset(config: Config):
    return build_langchain_tools(config.workspace_path)
```

先不要急着删 `ipilot/agent/tools/registry.py`。第 4 章以前，它还能作为旧链路保底。

## 7. 本章常见坑

### 坑 1：把工具继续包在 `ToolRegistry` 里

这会让你后面既要维护 LangChain tool，又要维护旧 registry。主路径上没有必要。

### 坑 2：一开始就把所有工具都改成 `ToolRuntime`

没必要。只有真的依赖 runtime context 的工具才需要。

### 坑 3：在 Windows 上把 `exec` 写死成类 Unix 命令习惯

当前开发环境是 PowerShell / Windows。教程里命令示例要尽量中性，或者明确说明平台差异。

## 8. 本章验证

建议加一个小测试，至少验证工具构造能工作：

```python
from ipilot.agent.langchain_tools import build_langchain_tools


def test_build_langchain_tools(tmp_path):
    tools = build_langchain_tools(tmp_path)
    names = sorted(tool.name for tool in tools)
    assert names == ["edit_file", "exec", "list_dir", "read_file", "write_file"]
```

然后跑：

```bash
uv run pytest -q tests/test_agent_loop.py
```

本章通过标准：

- LangChain tools 能构造成功
- 你已经明确主路径要从 `ToolRegistry` 切走
- 旧工具文件仍可保留，但不再是未来架构中心
