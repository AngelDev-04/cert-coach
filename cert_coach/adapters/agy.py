"""Agy CLI / Antigravity harness adapter."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from cert_coach.adapters.base import BaseHarnessAdapter
from cert_coach.core.config import TEMPLATES_DIR
from cert_coach.core.models import HarnessType
from cert_coach.exams.registry import ExamRegistry


class AgyCliAdapter(BaseHarnessAdapter):
    """Generates Antigravity CLI configuration (.gemini/rules/, .gemini/skills/, mcp.json)."""

    @property
    def harness_type(self) -> HarnessType:
        return HarnessType.AGY

    @property
    def display_name(self) -> str:
        return "Agy CLI (Antigravity)"

    @property
    def description(self) -> str:
        return "Installs Antigravity skills (.gemini/skills/), system rules (.gemini/rules/), and MCP wiring."

    def generate(
        self,
        workspace_root: Path,
        exam: str,
        db_path: Path,
        mcp_launch_cmd: list[str] | None = None,
    ) -> list[Path]:
        created: list[Path] = []
        exam_meta = ExamRegistry.get_metadata(exam)

        gemini_dir = workspace_root / ".gemini"
        rules_dir = gemini_dir / "rules"
        skills_dest = gemini_dir / "skills"
        rules_dir.mkdir(parents=True, exist_ok=True)
        skills_dest.mkdir(parents=True, exist_ok=True)

        # 1. Rules: question presentation contract
        rule_question_contract = rules_dir / "question-presentation-contract.md"
        rule_question_contract.write_text(
            f"""# {exam_meta.code} Question Presentation Contract

Applies to every flow that asks objective questions (quiz-learner, diagnostic-assessment, mock-exam).
A question must not be answerable from anything except its stem and options.

1. **Coverage-free headings**: Head each item with position only: `Question X of Y`. Never name domain, task, topic, or service under test before the learner answers.
2. **Vary key position**: Choose option order so the correct letter moves across A, B, C, D (max 40% in one slot).
3. **Balanced options**: Distractors must match the key in length, grammatical structure, and specificity.
4. **Format cues stay**: State single-answer or multiple-response (and how many to choose).
5. **Post-grading reveal**: Reveal canonical domain, task, topic, difficulty, and option-by-option rationale only AFTER grading.
""",
            encoding="utf-8",
        )
        created.append(rule_question_contract)

        # 2. Rules: privacy contract
        rule_privacy = rules_dir / "privacy-contract.md"
        rule_privacy.write_text(
            """# Privacy & Storage Contract

Never store question stems, option texts, or chat transcripts in SQLite persistence.
Only structured learning telemetry (domain/task/topic IDs, correctness booleans, difficulty, confidence, misconceptions, scenario rubrics) is saved via the `study-memory` MCP server.
""",
            encoding="utf-8",
        )
        created.append(rule_privacy)

        # 3. Copy Skills into .gemini/skills/
        skills_src = TEMPLATES_DIR / "skills"
        if skills_src.is_dir():
            for skill_dir in sorted(skills_src.glob("*")):
                if skill_dir.is_dir():
                    dest_skill_dir = skills_dest / skill_dir.name
                    dest_skill_dir.mkdir(parents=True, exist_ok=True)
                    for file in skill_dir.glob("*"):
                        dest_file = dest_skill_dir / file.name
                        shutil.copy2(file, dest_file)
                        created.append(dest_file)

        # 4. mcp.json
        workspace_server_py = (workspace_root / "study-memory-mcp" / "server.py").resolve()
        if workspace_server_py.is_file():
            server_py = workspace_server_py
        else:
            server_py = (TEMPLATES_DIR / "study-memory-mcp" / "server.py").resolve()

        mcp_json_path = workspace_root / "mcp.json"
        # If mcp.json already exists (e.g. from Kiro), merge or update study-memory
        mcp_data: dict = {"mcpServers": {}}
        if mcp_json_path.is_file():
            try:
                mcp_data = json.loads(mcp_json_path.read_text(encoding="utf-8"))
            except Exception:
                mcp_data = {"mcpServers": {}}

        mcp_data.setdefault("mcpServers", {})["study-memory"] = {
            "command": "python3",
            "args": [str(server_py)],
            "env": {
                "STUDY_MEMORY_DB": str(db_path.resolve())
            }
        }
        mcp_json_path.write_text(json.dumps(mcp_data, indent=2) + "\n", encoding="utf-8")
        created.append(mcp_json_path)

        return created

    def is_configured(self, workspace_root: Path) -> bool:
        return (workspace_root / ".gemini" / "rules").is_dir()

    def get_instructions(self, workspace_root: Path) -> str:
        return (
            "Agy CLI Setup:\n"
            f"  1. In terminal, navigate to: cd {workspace_root}\n"
            "  2. Launch Antigravity: agy\n"
            "  3. Try asking: 'Start an adaptive study plan for learner miguel'"
        )
