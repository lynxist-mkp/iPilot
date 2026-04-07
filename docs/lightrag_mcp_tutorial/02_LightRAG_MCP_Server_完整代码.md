# 第 2 章：LightRAG MCP Server 完整代码

这一章直接给你服务端整套代码。你要手敲的目标目录是：

```text
services/lightrag_mcp/
  __init__.py
  config.py
  path_resolver.py
  rag_service.py
  tool_handlers.py
  server.py
```

## 2.1 这一章先装什么

先确认依赖已经装好：

```bash
uv add "mcp[cli]" lightrag-hku
uv sync
```

如果这里 import 都过不去，后面的代码不要继续。

## 2.2 `services/lightrag_mcp/__init__.py`

这个文件可以先保持最小。

```python
"""LightRAG MCP server package."""
```

## 2.3 `services/lightrag_mcp/config.py`

这个文件只负责服务端配置，不碰业务。

```python
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _parse_csv(value: str | None, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


def _parse_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    return int(value)


def _parse_path(value: str | None, default: Path | None) -> Path | None:
    if value is None or not value.strip():
        return default
    return Path(value).expanduser().resolve()


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class LightRAGServerConfig:
    workspace_root: Path = field(default_factory=lambda: Path.cwd().expanduser().resolve())
    rag_working_dir: Path | None = None
    default_paths: list[str] = field(default_factory=lambda: ["README.md", "docs"])
    host: str = "127.0.0.1"
    port: int = 8091
    transport: str = "streamable-http"
    query_mode: str = "hybrid"
    top_k: int = 20
    encoding: str = "utf-8"
    text_suffixes: tuple[str, ...] = (".md", ".txt")
    llm_model_name: str = "qwen3.5-2b"
    embedding_model_name: str = "text-embedding-qwen3-embedding-0.6b"
    openai_api_key: str = "local-key"
    openai_base_url: str = "http://127.0.0.1:12721"
    embedding_dim: int = 1024
    working_dir_name: str = "workspace/rag/lightrag"

    def __post_init__(self) -> None:
        self.workspace_root = self.workspace_root.expanduser().resolve()
        if self.rag_working_dir is None:
            self.rag_working_dir = (self.workspace_root / self.working_dir_name).expanduser().resolve()
        else:
            self.rag_working_dir = self.rag_working_dir.expanduser().resolve()

    @property
    def working_dir(self) -> Path:
        assert self.rag_working_dir is not None
        return self.rag_working_dir


def load_server_config() -> LightRAGServerConfig:
    workspace_root = Path(
        os.getenv("LIGHTRAG_WORKSPACE_ROOT", str(Path.cwd()))
    ).expanduser().resolve()

    rag_working_dir = _parse_path(os.getenv("LIGHTRAG_WORKING_DIR"), None)
    default_paths = _parse_csv(os.getenv("LIGHTRAG_DEFAULT_PATHS"), ["README.md", "docs"])

    return LightRAGServerConfig(
        workspace_root=workspace_root,
        rag_working_dir=rag_working_dir,
        default_paths=default_paths,
        host=os.getenv("LIGHTRAG_HOST", "127.0.0.1"),
        port=_parse_int(os.getenv("LIGHTRAG_PORT"), 8091),
        transport=os.getenv("LIGHTRAG_TRANSPORT", "streamable-http"),
        query_mode=os.getenv("LIGHTRAG_QUERY_MODE", "hybrid"),
        top_k=_parse_int(os.getenv("LIGHTRAG_TOP_K"), 20),
        encoding=os.getenv("LIGHTRAG_ENCODING", "utf-8"),
        llm_model_name=os.getenv("LIGHTRAG_LLM_MODEL", "qwen3.5-2b"),
        embedding_model_name=os.getenv(
            "LIGHTRAG_EMBEDDING_MODEL", "text-embedding-qwen3-embedding-0.6b"
        ),
        openai_api_key=(
            os.getenv("LIGHTRAG_OPENAI_API_KEY")
            or os.getenv("LIGHTRAG_API_KEY")
            or "local-key"
        ),
        openai_base_url=(
            os.getenv("LIGHTRAG_OPENAI_BASE_URL")
            or os.getenv("LIGHTRAG_BASE_URL")
            or "http://127.0.0.1:12721"
        ),
        embedding_dim=_parse_int(os.getenv("LIGHTRAG_EMBEDDING_DIM"), 1024),
        working_dir_name=os.getenv("LIGHTRAG_WORKING_DIR_NAME", "workspace/rag/lightrag"),
    )
```

### 这段代码怎么读

- `LightRAGServerConfig` 只保存服务端需要的最小字段
- `load_server_config()` 从环境变量读配置
- `working_dir` 是默认知识库目录
- `default_paths` 默认指向工作区里的 `README.md` 和 `docs/`

### 完成标志

你应该能在 REPL 里这样看配置：

```python
from services.lightrag_mcp.config import load_server_config
cfg = load_server_config()
print(cfg.workspace_root)
print(cfg.working_dir)
print(cfg.default_paths)
```

## 2.4 `services/lightrag_mcp/path_resolver.py`

这个文件只做路径解析和安全检查。

```python
from __future__ import annotations

from pathlib import Path


TEXT_SUFFIXES: tuple[str, ...] = (".md", ".markdown", ".txt")


def _ensure_within_root(path: Path, workspace_root: Path) -> None:
    root = workspace_root.expanduser().resolve()
    candidate = path.expanduser().resolve()
    if candidate == root:
        return
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes workspace root: {candidate}") from exc


def _dedupe_sorted(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in sorted(paths, key=lambda item: item.as_posix()):
        key = path.as_posix()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def resolve_input_paths(workspace_root: Path, raw_paths: list[str]) -> list[Path]:
    workspace_root = workspace_root.expanduser().resolve()
    resolved: list[Path] = []

    for raw in raw_paths:
        candidate = Path(raw).expanduser()
        if candidate.is_absolute():
            absolute = candidate.resolve()
        else:
            absolute = (workspace_root / candidate).resolve()

        if not absolute.exists():
            raise FileNotFoundError(f"path does not exist: {absolute}")

        _ensure_within_root(absolute, workspace_root)
        resolved.append(absolute)

    return _dedupe_sorted(resolved)


def collect_indexable_files(
    workspace_root: Path,
    raw_paths: list[str],
    *,
    text_suffixes: tuple[str, ...] = TEXT_SUFFIXES,
) -> list[Path]:
    indexable: list[Path] = []
    candidates = resolve_input_paths(workspace_root, raw_paths)

    for candidate in candidates:
        if candidate.is_file():
            if candidate.suffix.lower() in text_suffixes:
                indexable.append(candidate)
            continue

        for child in candidate.rglob("*"):
            if not child.is_file():
                continue
            if child.suffix.lower() not in text_suffixes:
                continue
            _ensure_within_root(child, workspace_root)
            indexable.append(child.resolve())

    return _dedupe_sorted(indexable)
```

### 这段代码怎么读

- 所有路径默认相对 `workspace_root`
- 任何越界路径都直接报错
- 第一版只收文本文件
- 结果去重并排序，方便测试

### 完成标志

你应该能测出这三种情况：

```python
from pathlib import Path
from services.lightrag_mcp.path_resolver import collect_indexable_files

root = Path.cwd()
print(collect_indexable_files(root, ["README.md"]))
print(collect_indexable_files(root, ["docs"]))
```

## 2.5 `services/lightrag_mcp/rag_service.py`

这个文件封装 LightRAG 实例和三个核心动作。

```python
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import wrap_embedding_func_with_attrs

from .config import LightRAGServerConfig
from .path_resolver import collect_indexable_files


def _normalize_openai_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if not parsed.path or parsed.path == "/":
        path = "/v1"
    elif parsed.path.endswith("/v1"):
        path = parsed.path
    else:
        path = f"{parsed.path.rstrip('/')}/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def _normalize_query_result(result: Any) -> dict[str, Any]:
    if isinstance(result, str):
        return {"answer": result, "raw_type": "str"}

    if isinstance(result, dict):
        answer = result.get("answer") or result.get("response") or result.get("content")
        if answer is None:
            answer = json.dumps(result, ensure_ascii=False, default=str, indent=2)
        return {"answer": str(answer), "raw_type": "dict"}

    answer = getattr(result, "answer", None)
    if answer is None:
        answer = getattr(result, "response", None)
    if answer is None:
        answer = str(result)
    return {"answer": str(answer), "raw_type": type(result).__name__}


@dataclass(slots=True)
class LightRAGService:
    config: LightRAGServerConfig
    _rag: LightRAG | None = field(default=None, init=False, repr=False)
    _ready: bool = field(default=False, init=False, repr=False)

    def _build_llm_model_func(self):
        base_url = _normalize_openai_base_url(self.config.openai_base_url)
        api_key = self.config.openai_api_key
        model_name = self.config.llm_model_name

        async def llm_model_func(
            prompt: str,
            system_prompt: str | None = None,
            history_messages: list[dict[str, Any]] | None = None,
            enable_cot: bool = False,
            stream: bool | None = None,
            timeout: int | None = None,
            keyword_extraction: bool = False,
            **kwargs: Any,
        ) -> str:
            return await openai_complete_if_cache(
                model=model_name,
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages or [],
                enable_cot=enable_cot,
                base_url=base_url,
                api_key=api_key,
                stream=stream,
                timeout=timeout,
                keyword_extraction=keyword_extraction,
                **kwargs,
            )

        return llm_model_func

    def _build_embedding_func(self):
        default_base_url = _normalize_openai_base_url(self.config.openai_base_url)
        default_api_key = self.config.openai_api_key
        model_name = self.config.embedding_model_name
        embedding_dim = self.config.embedding_dim

        @wrap_embedding_func_with_attrs(
            embedding_dim=embedding_dim,
            max_token_size=8192,
            model_name=model_name,
        )
        async def embedding_func(
            texts: list[str],
            model: str = model_name,
            base_url: str | None = None,
            api_key: str | None = None,
            embedding_dim: int | None = None,
            max_token_size: int | None = None,
            client_configs: dict[str, Any] | None = None,
            token_tracker: Any | None = None,
            use_azure: bool = False,
            azure_deployment: str | None = None,
            api_version: str | None = None,
        ):
            return await openai_embed.func(
                texts=texts,
                model=model,
                base_url=base_url or default_base_url,
                api_key=api_key or default_api_key,
                embedding_dim=embedding_dim,
                max_token_size=max_token_size,
                client_configs=client_configs,
                token_tracker=token_tracker,
                use_azure=use_azure,
                azure_deployment=azure_deployment,
                api_version=api_version,
            )

        return embedding_func

    def _build_rag(self) -> LightRAG:
        return LightRAG(
            working_dir=str(self.config.working_dir),
            llm_model_func=self._build_llm_model_func(),
            llm_model_name=self.config.llm_model_name,
            embedding_func=self._build_embedding_func(),
            top_k=self.config.top_k,
            chunk_top_k=self.config.top_k,
        )

    async def ensure_ready(self) -> None:
        if self._ready and self._rag is not None:
            return

        self.config.working_dir.mkdir(parents=True, exist_ok=True)
        self._rag = self._build_rag()
        await self._rag.initialize_storages()
        self._ready = True

    async def close(self) -> None:
        if self._rag is None:
            return
        try:
            await self._rag.finalize_storages()
        finally:
            self._rag = None
            self._ready = False

    async def query(self, question: str, *, mode: str | None = None, top_k: int | None = None) -> dict[str, Any]:
        await self.ensure_ready()
        assert self._rag is not None

        query_mode = mode or self.config.query_mode
        query_kwargs: dict[str, Any] = {"mode": query_mode}
        if top_k is not None:
            query_kwargs["top_k"] = top_k

        raw_result = await self._rag.aquery(question, param=QueryParam(**query_kwargs))
        normalized = _normalize_query_result(raw_result)
        return {
            "question": question,
            "mode": query_mode,
            "top_k": top_k if top_k is not None else self.config.top_k,
            **normalized,
        }

    async def index_paths(self, raw_paths: list[str]) -> dict[str, Any]:
        await self.ensure_ready()
        assert self._rag is not None

        files = collect_indexable_files(
            self.config.workspace_root,
            raw_paths,
            text_suffixes=self.config.text_suffixes,
        )

        indexed_files: list[str] = []
        for file_path in files:
            content = file_path.read_text(encoding=self.config.encoding)
            rel_path = file_path.relative_to(self.config.workspace_root).as_posix()
            payload = f"Source: {rel_path}\n\n{content}"
            await self._rag.ainsert(payload)
            indexed_files.append(rel_path)

        return {
            "indexed_files": indexed_files,
            "count": len(indexed_files),
            "working_dir": str(self.config.working_dir),
        }

    async def rebuild(self, raw_paths: list[str] | None = None) -> dict[str, Any]:
        await self.close()
        if self.config.working_dir.exists():
            shutil.rmtree(self.config.working_dir)

        await self.ensure_ready()
        paths = raw_paths or list(self.config.default_paths)
        result = await self.index_paths(paths)
        result["rebuilt"] = True
        return result
```

### 这段代码怎么读

- `LightRAGService` 负责生命周期
- `ensure_ready()` 第一次调用时初始化 storages
- `query()` 包住 `LightRAG.aquery(...)`
- `index_paths()` 负责把文件内容塞进 LightRAG
- `rebuild()` 先清空 working dir，再重新建库

### 完成标志

先写一个小脚本，直接调 service：

```python
import asyncio
from services.lightrag_mcp.config import load_server_config
from services.lightrag_mcp.rag_service import LightRAGService

async def main():
    service = LightRAGService(load_server_config())
    print(await service.index_paths(["README.md", "docs"]))
    print(await service.query("这个项目现在的主链是什么？"))

asyncio.run(main())
```

## 2.6 `services/lightrag_mcp/tool_handlers.py`

这个文件只负责把 service 方法挂成 MCP tool handler。

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .rag_service import LightRAGService


@dataclass(slots=True)
class LightRAGToolHandlers:
    service: LightRAGService

    async def rag_query(self, question: str, mode: str = "hybrid", top_k: int | None = None) -> dict[str, Any]:
        return await self.service.query(question, mode=mode, top_k=top_k)

    async def rag_index_paths(self, paths: list[str]) -> dict[str, Any]:
        return await self.service.index_paths(paths)

    async def rag_rebuild(self, paths: list[str] | None = None) -> dict[str, Any]:
        return await self.service.rebuild(paths)
```

### 这段代码怎么读

- handler 不做业务
- handler 只透传参数
- 所有真正逻辑都留在 `rag_service.py`

## 2.7 `services/lightrag_mcp/server.py`

这个文件负责把 MCP server 组合起来。

```python
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import LightRAGServerConfig, load_server_config
from .rag_service import LightRAGService
from .tool_handlers import LightRAGToolHandlers


def build_server(config: LightRAGServerConfig | None = None) -> FastMCP:
    config = config or load_server_config()
    service = LightRAGService(config)
    handlers = LightRAGToolHandlers(service)

    mcp = FastMCP(
        "iPilot LightRAG MCP",
        json_response=True,
        stateless_http=True,
    )
    mcp.settings.host = config.host
    mcp.settings.port = config.port
    mcp.settings.streamable_http_path = "/mcp"

    @mcp.tool()
    async def rag_query(question: str, mode: str = "hybrid", top_k: int | None = None) -> dict[str, Any]:
        """Query the LightRAG knowledge base."""
        return await handlers.rag_query(question=question, mode=mode, top_k=top_k)

    @mcp.tool()
    async def rag_index_paths(paths: list[str]) -> dict[str, Any]:
        """Index a list of workspace-relative paths."""
        return await handlers.rag_index_paths(paths=paths)

    @mcp.tool()
    async def rag_rebuild(paths: list[str] | None = None) -> dict[str, Any]:
        """Rebuild the knowledge base from scratch."""
        return await handlers.rag_rebuild(paths=paths)

    return mcp


def main() -> None:
    config = load_server_config()
    server = build_server(config)
    server.run(transport=config.transport)


if __name__ == "__main__":
    main()
```

### 这段代码怎么读

- `FastMCP` 是 MCP server 入口
- `rag_query` / `rag_index_paths` / `rag_rebuild` 是第一版固定工具面
- `server.run(transport=config.transport)` 直接跑 `streamable-http`

### 完成标志

启动服务端：

```bash
uv run python -m services.lightrag_mcp.server
```

你应该能看到服务监听在 `127.0.0.1:8091`，并且后面章节能用 Inspector 看到 3 个工具。
