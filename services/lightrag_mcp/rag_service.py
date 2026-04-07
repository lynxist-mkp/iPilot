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
    normalized_path = parsed.path.rstrip("/")

    if not normalized_path:
        path = "/v1"
    elif normalized_path.endswith("/v1"):
        path = normalized_path
    else:
        path = f"{normalized_path}/v1"
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
