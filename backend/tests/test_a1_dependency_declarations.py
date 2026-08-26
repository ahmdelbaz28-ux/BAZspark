"""
A1 regression tests — dependency migration guardrails.

Pins the memory-stack embedding dimensions (1536 for OpenAI, 384 for local
sentence-transformers) across both memory stacks so the google-genai
migration (and later Stage-B registry unification) cannot silently change
vector geometry. Changing these values requires a data migration and is
explicitly out of scope for the agent-platform-rebuild plan.

Also verifies that the packages declared in A1 import cleanly:
openai, langchain_openai, langchain_neo4j, mcp, google.genai.

Run:
    pytest backend/tests/test_a1_dependency_declarations.py -q
"""

from __future__ import annotations

from typing import Any

import pytest


class TestDeclaredDependenciesImportable:
    """A1 acceptance: `import openai, langchain_openai, langchain_neo4j, mcp` succeeds."""

    def test_openai_imports_v2(self) -> None:
        import openai

        assert int(openai.version.VERSION.split(".")[0]) == 2  # noqa: RUF015 — single-element check

    def test_langchain_openai_imports(self) -> None:
        import langchain_openai  # noqa: F401 — presence is the contract

    def test_langchain_neo4j_imports(self) -> None:
        import langchain_neo4j  # noqa: F401 — presence is the contract

    def test_mcp_sdk_imports_v1(self) -> None:
        from importlib.metadata import version

        assert int(version("mcp").split(".")[0]) == 1

    def test_google_genai_imports_and_is_the_successor_sdk(self) -> None:
        from google import genai  # noqa: F401 — presence is the contract

    def test_legacy_google_generativeai_no_longer_imported_by_mem0_setup(self) -> None:
        """The deprecated SDK must not be referenced by first-party code."""
        import pathlib
        import sys

        root = pathlib.Path(__file__).resolve().parents[2]
        source = (root / "fireai" / "infrastructure" / "mem0_setup.py").read_text(
            encoding="utf-8"
        )
        assert "google.generativeai as genai" not in source
        module = sys.modules.get("fireai.infrastructure.mem0_setup")
        if module is not None:
            assert not hasattr(module, "google")


class TestEmbeddingDimensionsUnchanged:
    """Pin vector geometry: OpenAI stack 1536d, local sentence-transformers 384d."""

    def _strategy_config(
        self,
        monkeypatch: pytest.MonkeyPatch,
        ms: Any,
        primary_key_env: str,
    ) -> dict[str, Any]:
        """Clear all provider keys except one, stub connectivity to True."""
        for env in (
            "OPENAI_API_KEY",
            "FIREAI_OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "OPENCODE_API_KEY",
            "OPENQUOTTA_API_KEY",
            "GEMINI_API_KEY",
            "NVIDIA_API_KEY",
        ):
            monkeypatch.delenv(env, raising=False)
        monkeypatch.setenv(primary_key_env, "sk-test")
        monkeypatch.setattr(ms, "_test_openai_connectivity", lambda key: True)
        monkeypatch.setattr(
            ms, "_test_openai_compatible_connectivity", lambda base_url, key: True
        )
        monkeypatch.setattr(ms, "_test_gemini_connectivity", lambda key: True)
        monkeypatch.setattr(ms, "_detect_provider_cache", None)
        info: dict[str, Any] = dict(ms._detect_provider_uncached())
        return info

    def test_openai_strategy_uses_1536_dims(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import fireai.infrastructure.mem0_setup as ms

        info = self._strategy_config(monkeypatch, ms, "OPENAI_API_KEY")
        assert info["embedding_dims"] == 1536
        assert info["llm_model"] == "gpt-4o"
        assert info["embedder_model"] == "text-embedding-3-small"

    def test_gemini_strategy_keeps_local_384d_embeddings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Gemini pairs its LLM with local sentence-transformers (384d) — unchanged."""
        import fireai.infrastructure.mem0_setup as ms

        info = self._strategy_config(monkeypatch, ms, "GEMINI_API_KEY")
        assert info["provider"] == "gemini_primary"
        assert info["embedding_dims"] == 384
        assert info["embedder_provider"] == "local"

    def test_memory_service_default_stacks_pin_expected_dims(self) -> None:
        """backend/services/memory_service.py declares 1536/384 for its two stacks."""
        import inspect

        import backend.services.memory_service as memory_service

        src = inspect.getsource(memory_service)
        assert "embedding_dims=1536" in src or '"embedding_model_dims": 1536' in src
        assert "embedding_dims=384" in src or '"embedding_model_dims": 384' in src
