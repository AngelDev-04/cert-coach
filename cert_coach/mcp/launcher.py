"""Launcher for the stdio MCP server."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from cert_coach.core.config import TEMPLATES_DIR


def run_mcp_server(db_path: str | Path | None = None) -> None:
    """Launch the stdio MCP server process."""
    if db_path:
        os.environ["STUDY_MEMORY_DB"] = str(Path(db_path).resolve())

    # Check for study-memory-mcp in cwd, then fallback to embedded templates
    workspace_mcp = Path.cwd() / "study-memory-mcp"
    mcp_dir = workspace_mcp if workspace_mcp.is_dir() else (TEMPLATES_DIR / "study-memory-mcp")
    if str(mcp_dir) not in sys.path:
        sys.path.insert(0, str(mcp_dir))

    from server import main as server_main

    server_main()
