"""Core data models for cert-coach workspaces, exams, and harnesses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class HarnessType(str, Enum):
    """Supported AI agent harnesses."""

    KIRO = "kiro"
    CLAUDE = "claude"
    AGY = "agy"
    CODEX = "codex"

    @classmethod
    def from_string(cls, value: str) -> HarnessType:
        normalized = value.strip().lower()
        if normalized in ("kiro", "kiro-cli", "kiro_cli"):
            return cls.KIRO
        if normalized in ("claude", "claude-code", "claude_code"):
            return cls.CLAUDE
        if normalized in ("agy", "agy-cli", "agy_cli", "antigravity"):
            return cls.AGY
        if normalized in ("codex", "codex-cli", "codex_cli", "openai-codex", "openai_codex"):
            return cls.CODEX
        raise ValueError(f"Unknown harness '{value}'. Supported: kiro, claude, agy, codex")


class ExamType(str, Enum):
    """Supported certification exam tracks."""

    SAA_C03 = "saa-c03"
    CLF_C02 = "clf-c02"
    AIF_C01 = "aif-c01"

    @classmethod
    def from_string(cls, value: str) -> ExamType:
        normalized = value.strip().lower().replace("_", "-")
        for exam in cls:
            if exam.value == normalized:
                return exam
        valid = ", ".join(e.value for e in cls)
        raise ValueError(f"Unknown exam '{value}'. Supported: {valid}")


@dataclass(frozen=True)
class ExamMetadata:
    """Metadata describing a certification exam track."""

    code: str
    name: str
    description: str
    domains_count: int
    tasks_count: int
    status: str = "active"


@dataclass
class WorkspaceConfig:
    """Persistent workspace configuration saved in .cert-coach.json."""

    exam: str
    harnesses: list[str] = field(default_factory=list)
    database_path: str = ""
    version: str = "1.0"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkspaceConfig:
        return cls(
            exam=data.get("exam", "saa-c03"),
            harnesses=data.get("harnesses", []),
            database_path=data.get("database_path", ""),
            version=data.get("version", "1.0"),
            created_at=data.get("created_at", ""),
        )

    def resolve_db_path(self, workspace_root: Path) -> Path:
        """Resolve the effective SQLite database path."""
        if not self.database_path:
            return Path.home() / ".cert-coach" / "study-memory.sqlite3"
        raw = Path(self.database_path).expanduser()
        if raw.is_absolute():
            return raw
        return (workspace_root / raw).resolve()
