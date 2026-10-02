"""Base class and interface for AI agent harness adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from cert_coach.core.models import HarnessType


class BaseHarnessAdapter(ABC):
    """Abstract base adapter for scaffolding harness-specific integration files."""

    @property
    @abstractmethod
    def harness_type(self) -> HarnessType:
        """The harness identifier."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable harness name."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description of the harness integration."""

    @abstractmethod
    def generate(
        self,
        workspace_root: Path,
        exam: str,
        db_path: Path,
        mcp_launch_cmd: list[str] | None = None,
    ) -> list[Path]:
        """Generate all harness-specific configuration and skill files.

        Returns a list of created file paths.
        """

    @abstractmethod
    def is_configured(self, workspace_root: Path) -> bool:
        """Check if this harness is currently configured in the workspace."""

    @abstractmethod
    def get_instructions(self, workspace_root: Path) -> str:
        """Return user-facing instructions on how to use this harness."""
