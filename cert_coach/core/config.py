"""Workspace configuration manager for cert-coach projects."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from cert_coach.core.models import WorkspaceConfig

CONFIG_FILENAME = ".cert-coach.json"
DEFAULT_SHARED_DB = Path.home() / ".cert-coach" / "study-memory.sqlite3"
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"

WORKSPACE_HOME_ENV = "CERT_COACH_HOME"
WORKSPACE_DIRNAME = "cert-coach"


def default_workspace_root() -> Path:
    """Return the fixed, cwd-independent default study workspace location.

    Uses ``$CERT_COACH_HOME`` when set, otherwise ``~/cert-coach``. Evaluated at
    call time so the environment variable and home directory are always honored.
    """
    override = os.environ.get(WORKSPACE_HOME_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / WORKSPACE_DIRNAME).resolve()


STATE_DIR_ENV = "CERT_COACH_STATE_DIR"
WORKSPACE_POINTER_FILENAME = "workspace.json"


def state_dir() -> Path:
    """Return the per-user state folder (``$CERT_COACH_STATE_DIR`` or ``~/.cert-coach``)."""
    override = os.environ.get(STATE_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".cert-coach").resolve()


def create_private_file(path: Path) -> None:
    """Create ``path`` with owner-only permissions (0600) unless it already exists.

    Learner memory holds flashcard answers and study history, so it must not be
    world-readable on shared machines. Existing files are left untouched.
    """
    try:
        os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    except FileExistsError:
        pass


def read_workspace_pointer() -> Path | None:
    """Return the registered workspace root if it still holds a workspace manifest."""
    pointer = state_dir() / WORKSPACE_POINTER_FILENAME
    try:
        data = json.loads(pointer.read_text(encoding="utf-8"))
        root = Path(data["path"]).expanduser().resolve()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return root if (root / CONFIG_FILENAME).is_file() else None


def write_workspace_pointer(root: Path) -> None:
    """Register ``root`` as this user's single study workspace."""
    folder = state_dir()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    (folder / WORKSPACE_POINTER_FILENAME).write_text(
        json.dumps({"path": str(root.resolve())}, indent=2) + "\n", encoding="utf-8"
    )


def find_existing_workspace() -> Path | None:
    """Locate this user's workspace: the registered pointer, else the default root."""
    registered = read_workspace_pointer()
    if registered is not None:
        return registered
    default_root = default_workspace_root()
    return default_root if (default_root / CONFIG_FILENAME).is_file() else None


# Snapshot of the default at import time (prefer default_workspace_root() at runtime).
DEFAULT_WORKSPACE_ROOT = default_workspace_root()


class WorkspaceManager:
    """Manages workspace detection, configuration persistence, and paths."""

    def __init__(self, root: Path | str | None = None) -> None:
        target = Path(root).resolve() if root else Path.cwd().resolve()
        # If target has an isolated cert-coach subdirectory with config, resolve to it
        if not (target / CONFIG_FILENAME).is_file() and (target / "cert-coach" / CONFIG_FILENAME).is_file():
            self.root = target / "cert-coach"
        else:
            self.root = target

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
