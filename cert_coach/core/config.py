"""Workspace configuration manager for cert-coach projects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cert_coach.core.models import WorkspaceConfig

CONFIG_FILENAME = ".cert-coach.json"
DEFAULT_SHARED_DB = Path.home() / ".cert-coach" / "study-memory.sqlite3"
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


class WorkspaceManager:
    """Manages workspace detection, configuration persistence, and paths."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root).resolve() if root else Path.cwd()

    @property
    def config_file(self) -> Path:
        return self.root / CONFIG_FILENAME

    def is_initialized(self) -> bool:
        """Check if the current workspace has been initialized."""
        return self.config_file.is_file()

    def load_config(self) -> WorkspaceConfig:
        """Load the workspace configuration file or raise FileNotFoundError."""
        if not self.is_initialized():
            raise FileNotFoundError(
                f"Workspace at '{self.root}' is not initialized. "
                f"Run 'cert-coach init' to configure it."
            )
        with self.config_file.open(encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
        return WorkspaceConfig.from_dict(data)

    def save_config(self, config: WorkspaceConfig) -> Path:
        """Save the workspace configuration file."""
        self.root.mkdir(parents=True, exist_ok=True)
        with self.config_file.open("w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2)
        return self.config_file

    def add_harness(self, harness: str) -> WorkspaceConfig:
        """Add a harness to an existing workspace configuration."""
        config = self.load_config()
        if harness not in config.harnesses:
            config.harnesses.append(harness)
            self.save_config(config)
        return config
