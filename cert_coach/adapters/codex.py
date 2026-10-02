"""OpenAI Codex CLI harness adapter."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from cert_coach.adapters.base import BaseHarnessAdapter
from cert_coach.core.config import TEMPLATES_DIR
from cert_coach.core.models import HarnessType
from cert_coach.exams.registry import ExamRegistry


class CodexAdapter(BaseHarnessAdapter):
    """Generates OpenAI Codex CLI configuration (AGENTS.md, CODEX.md, .codex/config.toml, .agents/skills/)."""

    @property
    def harness_type(self) -> HarnessType:
        return HarnessType.CODEX

    @property
    def display_name(self) -> str:
        return "OpenAI Codex CLI"

    @property
    def description(self) -> str:
        return "Installs Codex configuration (.codex/config.toml, AGENTS.md, CODEX.md, .agents/skills/)."

    def generate(
        self,
        workspace_root: Path,
        exam: str,
        db_path: Path,
        mcp_launch_cmd: list[str] | None = None,
    ) -> list[Path]:
        created: list[Path] = []
        exam_meta = ExamRegistry.get_metadata(exam)

        # 1. AGENTS.md (Primary instruction file for Codex)
        agents_md_path = workspace_root / "AGENTS.md"
        agents_content = f"""# {exam_meta.name} ({exam_meta.code}) Study Coach - Codex Instructions

You are an expert, privacy-first study coach for the **{exam_meta.name} ({exam_meta.code})** certification exam.
Equipped with 9 specialized study skills and a local persistent learner-memory MCP server (`study-memory`), you guide the learner through diagnostics, adaptive practice quizzes, weighted mock exams, architectural scenario drills, and spaced repetition flashcards.

---

## Strict Question Presentation Contract
Applies to EVERY objective question flow (quizzes, diagnostics, mock exams):
1. **Coverage-Free Headings**: Head each item with position only (`Question X of Y`). NEVER name the domain, task, topic, difficulty, or service under test before the learner answers (e.g. heading `Question 1 of 10 — Aurora Global Database` invalidates the test).
2. **Vary Key Position**: Distribute the correct answer evenly across A, B, C, D. No single position should hold the key in more than 40% of items in a set.
3. **Balanced Options**: Distractors must match the key in length, grammatical structure, and technical specificity. The longest or most detailed option must not be reliably correct.
4. **Format Cues**: Explicitly state whether the question is single-answer or multiple-response (and how many options to select).
5. **Post-Grading Reveal**: Reveal the canonical domain, task statement, topic, difficulty, and option-by-option rationale ONLY AFTER the learner submits their answer.

---

## Privacy & Persistence Contract
- Never store question stems, option text, or chat transcripts in SQLite persistence.
- Only record structured telemetry via `study-memory` MCP tools: canonical `topic_id`, boolean correctness (`is_correct`), `confidence`, and concise misconception tags.
- All learner memory is stored locally in the configured SQLite database.

---

## Available Study Skills
The workspace includes 9 specialized skills located in `.agents/skills/` (callable by intent or via `$ <skill-name>`):
1. **`diagnostic-assessment`**: 14-question baseline sampling all official tasks with feedback withheld until the end.
2. **`mock-exam`**: Timed-style mini (20Q) or full (65Q) mock exam adhering to official domain weights with delayed scoring.
3. **`quiz-learner`**: Targeted adaptive practice on requested domains or topics with immediate option-by-option rationales.
4. **`scenario-drill`**: Real-world architectural trade-off design problem scored on a 5-dimension rubric (0-4 points).
5. **`flashcard-review`**: Active-recall spaced repetition review (SM-2 schedule) hiding answers during recall.
6. **`adaptive-study-plan`**: Daily study recommendations calibrated by exam deadlines, due cards, and low-evidence tasks.
7. **`review-progress`**: Comprehensive mastery dashboard covering domain coverage, misconceptions, and confidence calibration.
8. **`teach-topic`**: Concept deep-dive contrasting architectural trade-offs, service selection rules, and exam pitfalls.
9. **`question-quality`**: Audits questions against `docs/question-quality-rubric.md` ensuring complete stems and plausible distractors.

---

## Local MCP Server (`study-memory`)
Codex interacts with the local stdio MCP server configured in `.codex/config.toml`:
- `get_exam_catalog`: Look up canonical tasks, topics, selection rules, and confusions.
- `set_learner_profile` / `get_learner_profile`: Manage study goals, exam date, and weekly hours.
- `start_study_session` / `get_study_session` / `complete_study_session`: Manage session state.
- `record_quiz_attempt`: Idempotently log objective and scenario attempts.
- `get_progress`: Fetch mastery, coverage, and misconception telemetry.
- `get_study_recommendation`: Retrieve high-yield recommended topics.
- `save_flashcard` / `get_due_flashcards` / `get_flashcard_answer` / `review_flashcard`: SM-2 spaced repetition.

---

## Common Prompt Triggers
- "Start an initial diagnostic for learner miguel"
- "Quiz learner miguel on DynamoDB vs Aurora with 3 questions"
- "Start a 20-question mini mock exam for learner miguel"
- "Give me an architecture scenario drill on resilient multi-tier VPC design"
- "Review my due flashcards for learner miguel"
- "What should learner miguel study today?"
"""
        agents_md_path.write_text(agents_content, encoding="utf-8")
        created.append(agents_md_path)

        # 2. CODEX.md (Codex-specific fallback instruction file)
        codex_md_path = workspace_root / "CODEX.md"
        codex_content = f"""# {exam_meta.name} ({exam_meta.code}) Study Coach - Codex CLI Configuration

This workspace is configured for the **{exam_meta.name} ({exam_meta.code})** Study Coach.

Please refer to `AGENTS.md` for full instructions, capabilities, and contracts.

## Key Rules
1. **Question Presentation Contract**: Head items with `Question X of Y` only. Do not reveal domain, task, or topic before the user answers. Balance distractors and vary key positions.
2. **Privacy Contract**: Never persist question stems or conversation transcripts. Store only structured telemetry via `study-memory` MCP tools.
3. **Skills**: Modular skills are available in `.agents/skills/` and `.codex/skills/`.
"""
        codex_md_path.write_text(codex_content, encoding="utf-8")
        created.append(codex_md_path)

        # 3. .codex/config.toml (Project-scoped MCP configuration)
        codex_dir = workspace_root / ".codex"
        codex_dir.mkdir(parents=True, exist_ok=True)
        config_toml_path = codex_dir / "config.toml"

        workspace_server_py = (workspace_root / "study-memory-mcp" / "server.py").resolve()
        if workspace_server_py.is_file():
            server_py = workspace_server_py
        else:
            server_py = (TEMPLATES_DIR / "study-memory-mcp" / "server.py").resolve()

        escaped_server = str(server_py).replace("\\", "\\\\")
        escaped_db = str(db_path.resolve()).replace("\\", "\\\\")

        mcp_block = (
            "[mcp_servers.study-memory]\n"
            'command = "python3"\n'
            f'args = ["{escaped_server}"]\n\n'
            "[mcp_servers.study-memory.env]\n"
            f'STUDY_MEMORY_DB = "{escaped_db}"\n'
        )

        if config_toml_path.is_file():
            existing_toml = config_toml_path.read_text(encoding="utf-8")
            if "[mcp_servers.study-memory]" in existing_toml:
                pattern = r"\[mcp_servers\.study-memory\][\s\S]*?(?=\n\[|\Z)"
                new_toml = re.sub(pattern, mcp_block.strip(), existing_toml)
            else:
                new_toml = existing_toml.rstrip() + "\n\n" + mcp_block
            config_toml_path.write_text(new_toml.strip() + "\n", encoding="utf-8")
        else:
            config_toml_path.write_text(mcp_block, encoding="utf-8")
        created.append(config_toml_path)

        # 4. Copy Skills to .agents/skills/ and .codex/skills/
        skills_src = TEMPLATES_DIR / "skills"
        dest_dirs = [
            workspace_root / ".agents" / "skills",
            workspace_root / ".codex" / "skills",
        ]

        if skills_src.is_dir():
            for target_skills_dir in dest_dirs:
                target_skills_dir.mkdir(parents=True, exist_ok=True)
                for skill_dir in sorted(skills_src.glob("*")):
                    if skill_dir.is_dir():
                        dest_skill_dir = target_skills_dir / skill_dir.name
                        dest_skill_dir.mkdir(parents=True, exist_ok=True)
                        for file in skill_dir.glob("*"):
                            dest_file = dest_skill_dir / file.name
                            shutil.copy2(file, dest_file)
                            created.append(dest_file)

        return created

    def is_configured(self, workspace_root: Path) -> bool:
        return (
            (workspace_root / "AGENTS.md").is_file()
            and (workspace_root / ".codex" / "config.toml").is_file()
        )

    def get_instructions(self, workspace_root: Path) -> str:
        return (
            "OpenAI Codex CLI Setup:\n"
            f"  1. In terminal, navigate to: cd {workspace_root}\n"
            "  2. Launch Codex: codex\n"
            "  3. Try asking: 'Start an initial diagnostic for learner miguel'\n"
            "     or run: '$ quiz-learner' or 'What should learner miguel study today?'"
        )
