from __future__ import annotations

import importlib
import sys
import types


def _install_lightrag_stubs(monkeypatch):
    lightrag = types.ModuleType("lightrag")
    lightrag.__path__ = []  # type: ignore[attr-defined]

    class FakeLightRAG:
        pass

    class FakeQueryParam:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    lightrag.LightRAG = FakeLightRAG
    lightrag.QueryParam = FakeQueryParam

    llm = types.ModuleType("lightrag.llm")
    llm.__path__ = []  # type: ignore[attr-defined]

    openai = types.ModuleType("lightrag.llm.openai")

    async def openai_complete_if_cache(*args, **kwargs):
        return "stub"

    class FakeOpenAIEmbed:
        async def func(self, *args, **kwargs):
            return []

    openai.openai_complete_if_cache = openai_complete_if_cache
    openai.openai_embed = FakeOpenAIEmbed()
    llm.openai = openai
    lightrag.llm = llm

    utils = types.ModuleType("lightrag.utils")

    def wrap_embedding_func_with_attrs(**attrs):
        def decorator(fn):
            return fn

        return decorator

    utils.wrap_embedding_func_with_attrs = wrap_embedding_func_with_attrs
    lightrag.utils = utils

    monkeypatch.setitem(sys.modules, "lightrag", lightrag)
    monkeypatch.setitem(sys.modules, "lightrag.llm", llm)
    monkeypatch.setitem(sys.modules, "lightrag.llm.openai", openai)
    monkeypatch.setitem(sys.modules, "lightrag.utils", utils)


def test_normalize_openai_base_url_preserves_existing_v1_suffix(monkeypatch):
    _install_lightrag_stubs(monkeypatch)
    monkeypatch.delitem(sys.modules, "services.lightrag_mcp.rag_service", raising=False)

    rag_service = importlib.import_module("services.lightrag_mcp.rag_service")

    assert rag_service._normalize_openai_base_url("http://127.0.0.1:12721/v1/") == "http://127.0.0.1:12721/v1"
    assert rag_service._normalize_openai_base_url("http://127.0.0.1:12721/openai/v1/") == "http://127.0.0.1:12721/openai/v1"
    assert rag_service._normalize_openai_base_url("http://127.0.0.1:12721") == "http://127.0.0.1:12721/v1"
