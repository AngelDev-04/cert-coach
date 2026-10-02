"""Kiro IDE and Kiro-CLI harness adapter."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from cert_coach.adapters.base import BaseHarnessAdapter
from cert_coach.adapters.pacing import TURN_TAKING_CONTRACT
from cert_coach.core.config import TEMPLATES_DIR
from cert_coach.core.models import HarnessType
from cert_coach.exams.registry import ExamRegistry


class KiroAdapter(BaseHarnessAdapter):
    """Generates Kiro Power configuration (POWER.md, mcp.json, steering/, skills/)."""

    @property
    def harness_type(self) -> HarnessType:
        return HarnessType.KIRO

    @property
    def display_name(self) -> str:
        return "Kiro / Kiro-CLI"

    @property
    def description(self) -> str:
        return "Installs as a Kiro Power with local MCP server, steering rules, and 9 study skills."

    def generate(
        self,
        workspace_root: Path,
        exam: str,
        db_path: Path,
        mcp_launch_cmd: list[str] | None = None,
    ) -> list[Path]:
        created: list[Path] = []
        exam_meta = ExamRegistry.get_metadata(exam)

        # 1. POWER.md
        power_md_path = workspace_root / "POWER.md"
        power_content = f"""---
name: "{exam_meta.code.lower()}-study-coach"
displayName: "{exam_meta.name} Study Coach"
description: "Adaptive {exam_meta.name} ({exam_meta.code}) study coach with local learner memory, diagnostics, weighted mocks, quizzes, scenario drills, flashcards, and progress tracking"
keywords: ["aws", "{exam_meta.code.lower()}", "certification", "study-coach", "adaptive-learning"]
author: "AWS Study Coach contributors"
---

# {exam_meta.name} Study Coach Power

An adaptive, privacy-first study coach for the **{exam_meta.name} ({exam_meta.code})** examination.
Equipped with 9 specialized study skills powered by a local, persistent learner-memory MCP server.

> **Privacy Contract:** Never stores question stems or chat transcripts. Only structured telemetry is saved locally.

---

{TURN_TAKING_CONTRACT}
Full contracts live in `steering/steering.md`, which is loaded on every session.
"""
        power_md_path.write_text(power_content, encoding="utf-8")
        created.append(power_md_path)

        # 2. plugin.json
        plugin_json_path = workspace_root / "plugin.json"
        plugin_data = {
            "$schema": "https://raw.githubusercontent.com/kiro-editor/powers/main/schemas/power-v1.json",
            "name": f"{exam_meta.code.lower()}-study-coach",
            "version": "0.3.0",
            "description": f"Adaptive {exam_meta.code} study coach with local learner memory.",
            "keywords": ["aws", exam_meta.code.lower(), "study-coach"],
        }
        plugin_json_path.write_text(json.dumps(plugin_data, indent=2) + "\n", encoding="utf-8")
        created.append(plugin_json_path)

        # 3. mcp.json
        mcp_json_path = workspace_root / "mcp.json"
        # Determine path to MCP server.py (prefer workspace copy, fallback to embedded templates)
        workspace_server_py = (workspace_root / "study-memory-mcp" / "server.py").resolve()
        if workspace_server_py.is_file():
            server_py = workspace_server_py
        else:
            server_py = (TEMPLATES_DIR / "study-memory-mcp" / "server.py").resolve()

        mcp_data = {
            "$schema": "https://raw.githubusercontent.com/kiro-editor/powers/main/schemas/mcp-v1.json",
            "mcpServers": {
                "study-memory": {
                    "command": "python3",
                    "args": [str(server_py)],
                    "env": {
                        "STUDY_MEMORY_DB": str(db_path.resolve())
                    }
                }
            }
        }
        mcp_json_path.write_text(json.dumps(mcp_data, indent=2) + "\n", encoding="utf-8")
        created.append(mcp_json_path)

        # 4. steering/steering.md
        steering_dir = workspace_root / "steering"
        steering_dir.mkdir(parents=True, exist_ok=True)
        steering_path = steering_dir / "steering.md"
        src_steering = TEMPLATES_DIR / "steering" / "steering.md"
        if src_steering.is_file():
            shutil.copy2(src_steering, steering_path)
        else:
            steering_path.write_text(
                "---\ninclusion: always\n---\n\n# Study Coach Steering\n\n"
                + TURN_TAKING_CONTRACT
                + "\nFollow Question Presentation Contract.\n",
                encoding="utf-8"
            )
        created.append(steering_path)

        # 5. skills/
        skills_src = TEMPLATES_DIR / "skills"
        skills_dest = workspace_root / "skills"
        if skills_src.is_dir():
            for skill_dir in sorted(skills_src.glob("*")):
                if skill_dir.is_dir():
                    dest_skill_dir = skills_dest / skill_dir.name
                    dest_skill_dir.mkdir(parents=True, exist_ok=True)
                    for file in skill_dir.glob("*"):
                        dest_file = dest_skill_dir / file.name
                        shutil.copy2(file, dest_file)
                        created.append(dest_file)

        return created

    def is_configured(self, workspace_root: Path) -> bool:
        return (workspace_root / "POWER.md").is_file() and (workspace_root / "mcp.json").is_file()

    def get_instructions(self, workspace_root: Path) -> str:
        return (
            "Kiro Setup:\n"
            "  1. Open Kiro -> Powers -> Add Custom Power -> Import power from a folder\n"
            f"  2. Select: {workspace_root}\n"
            "  3. In Kiro chat, test: 'Start a diagnostic for learner-01'\n"
            f"  Kiro CLI: cd {workspace_root} && kiro-cli"
        )
