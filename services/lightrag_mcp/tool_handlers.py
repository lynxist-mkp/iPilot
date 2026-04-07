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
