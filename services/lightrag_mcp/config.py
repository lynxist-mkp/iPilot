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
