"""Harness adapter registry and exports."""

from __future__ import annotations

from cert_coach.adapters.agy import AgyCliAdapter
from cert_coach.adapters.base import BaseHarnessAdapter
from cert_coach.adapters.claude import ClaudeCodeAdapter
from cert_coach.adapters.codex import CodexAdapter
from cert_coach.adapters.kiro import KiroAdapter
from cert_coach.core.models import HarnessType

_ADAPTERS: dict[HarnessType, BaseHarnessAdapter] = {
    HarnessType.KIRO: KiroAdapter(),
    HarnessType.CLAUDE: ClaudeCodeAdapter(),
    HarnessType.AGY: AgyCliAdapter(),
    HarnessType.CODEX: CodexAdapter(),
}


def get_adapter(harness: str | HarnessType) -> BaseHarnessAdapter:
    """Retrieve an adapter by harness enum or string."""
    h_type = harness if isinstance(harness, HarnessType) else HarnessType.from_string(harness)
    if h_type not in _ADAPTERS:
        raise ValueError(f"No adapter registered for harness '{harness}'")
    return _ADAPTERS[h_type]


def list_adapters() -> list[BaseHarnessAdapter]:
    """List all available harness adapters."""
    return list(_ADAPTERS.values())


__all__ = [
    "AgyCliAdapter",
    "BaseHarnessAdapter",
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "KiroAdapter",
    "get_adapter",
    "list_adapters",
]
