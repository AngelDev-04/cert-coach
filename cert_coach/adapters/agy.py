"""Agy CLI / Antigravity harness adapter."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from cert_coach.adapters.base import BaseHarnessAdapter
from cert_coach.core.config import TEMPLATES_DIR
from cert_coach.core.models import HarnessType
from cert_coach.exams.registry import ExamRegistry

QUESTION_CONTRACT_CONTENT = """# {exam_code} Question Presentation Contract

Applies to every flow that asks objective questions (quiz-learner, diagnostic-assessment, mock-exam).
A question must not be answerable from anything except its stem and options.

1. **Coverage-free headings**: Head each item with position only: `Question X of Y`. Never name domain, task, topic, or service under test before the learner answers.
2. **Vary key position**: Choose option order so the correct letter moves across A, B, C, D (max 40% in one slot).
3. **Balanced options**: Distractors must match the key in length, grammatical structure, and specificity.
4. **Format cues stay**: State single-answer or multiple-response (and how many to choose).
5. **Post-grading reveal**: Reveal canonical domain, task, topic, difficulty, and option-by-option rationale only AFTER grading.
"""

PRIVACY_CONTRACT_CONTENT = """# Privacy & Storage Contract

Never store question stems, option texts, or chat transcripts in SQLite persistence.
Only structured learning telemetry (domain/task/topic IDs, correctness booleans, difficulty, confidence, misconceptions, scenario rubrics) is saved via the `study-memory` MCP server.
All data stays on the learner's local machine.
"""


class AgyCliAdapter(BaseHarnessAdapter):
    """Generates complete Google Antigravity / Agy CLI configuration.

    Creates:
      - GEMINI.md (Workspace root instructions & rules)
      - .agents/skills/ & .gemini/skills/ (9 canonical skills + shorthand aliases)
      - .agents/rules/ & .gemini/rules/ (Presentation & Privacy contracts)
      - .agents/skills.json (Declared skill configuration)
      - mcp_config.json & mcp.json (Antigravity & Kiro MCP wiring)
    """

    @property
    def harness_type(self) -> HarnessType:
        return HarnessType.AGY

    @property
    def display_name(self) -> str:
        return "Agy CLI (Antigravity)"

    @property
    def description(self) -> str:
        return "Installs Antigravity skills (.agents/skills/ & .gemini/skills/), system rules (GEMINI.md), and MCP wiring."

    def generate(
        self,
        workspace_root: Path,
        exam: str,
        db_path: Path,
        mcp_launch_cmd: list[str] | None = None,
    ) -> list[Path]:
        created: list[Path] = []
        exam_meta = ExamRegistry.get_metadata(exam)

        # 1. Master Workspace Rule: GEMINI.md
        gemini_md_path = workspace_root / "GEMINI.md"
        gemini_md_content = f"""# {exam_meta.name} ({exam_meta.code}) Study Coach - Antigravity Instructions

You are an expert, adaptive, and privacy-first study coach for the **{exam_meta.name} ({exam_meta.code})** examination.
You guide the learner through personalized diagnostics, targeted quizzes, architecture scenario drills, spaced repetition flashcards, and weighted mock exams using the local `study-memory` MCP server.

---

## Strict Question Presentation Contract
Applies to EVERY flow asking objective questions (`quiz-learner`, `diagnostic-assessment`, `mock-exam`):
1. **Coverage-free headings**: Head each question ONLY with its position: `Question X of Y`. NEVER name the domain, task, topic, difficulty, or service under test before the learner answers.
2. **Vary key position**: Distribute the correct answer evenly across A, B, C, D (max 40% in one position across any set of 10+ items).
3. **Balanced options**: Distractors must match the key in length, grammar, and technical detail. The longest or most detailed option must not be reliably correct.
4. **Format cues**: State whether the question is single-answer or multiple-response (and exactly how many to choose).
5. **Post-grading reveal**: Reveal canonical domain, task, topic, difficulty, and option-by-option rationales ONLY AFTER the learner submits their answer.

---

## Privacy & Persistence Contract
- Never store question stems, option text, or transcripts in SQLite.
- Only record structured learning telemetry: canonical topic_id, correctness (bool), confidence, and concise misconception tags.
- Always use the tools provided by the `study-memory` MCP server.

---

## Available Antigravity Study Skills & Slash Commands
- `/<diagnostic-assessment>` (or `/<diagnostic>`): 14-question baseline sampling all official tasks with feedback withheld until completion.
- `/<quiz-learner>` (or `/<quiz>`): Targeted adaptive quizzes on requested domains/topics with immediate option rationales.
- `/<mock-exam>` (or `/<mock>`): Timed-style mini (20Q) or full (65Q) exam following official domain weights.
- `/<flashcard-review>` (or `/<flashcards>`): Answer-hidden active recall review with Again/Hard/Good/Easy spaced repetition.
- `/<review-progress>` (or `/<progress>`): Visual knowledge dashboard, mastery breakdown, and next study recommendations.
- `/<scenario-drill>` (or `/<scenario>`): Architecture trade-off drills evaluated on a 0–4 multidimensional rubric.
- `/<teach-topic>` (or `/<teach>`): SAA-C03 deep dives with comparative decision rules and common confusions.
- `/<adaptive-study-plan>`: Builds concrete, time-bounded study sessions based on due cards and lowest-mastery tasks.
- `/<question-quality>`: Audits practice questions against the quality rubric to prevent leaks, ambiguity, or poor distractors.
"""
        gemini_md_path.write_text(gemini_md_content, encoding="utf-8")
        created.append(gemini_md_path)

        # 2. Rule directories: .gemini/rules/ AND .agents/rules/
        gemini_rules = workspace_root / ".gemini" / "rules"
        agents_rules = workspace_root / ".agents" / "rules"
        gemini_rules.mkdir(parents=True, exist_ok=True)
        agents_rules.mkdir(parents=True, exist_ok=True)

        q_contract_text = QUESTION_CONTRACT_CONTENT.format(exam_code=exam_meta.code)

        # question-presentation-contract.md (for backward-compatibility with tests)
        rule_q_legacy = gemini_rules / "question-presentation-contract.md"
        rule_q_legacy.write_text(q_contract_text, encoding="utf-8")
        created.append(rule_q_legacy)

        # question-contract.md (standard contract name)
        for r_dir in (gemini_rules, agents_rules):
            r_file = r_dir / "question-contract.md"
            r_file.write_text(q_contract_text, encoding="utf-8")
            created.append(r_file)

        # privacy-contract.md
        for r_dir in (gemini_rules, agents_rules):
            p_file = r_dir / "privacy-contract.md"
            p_file.write_text(PRIVACY_CONTRACT_CONTENT, encoding="utf-8")
            created.append(p_file)

        # 3. Copy Skills into .gemini/skills/ AND .agents/skills/
        gemini_skills = workspace_root / ".gemini" / "skills"
        agents_skills = workspace_root / ".agents" / "skills"
        gemini_skills.mkdir(parents=True, exist_ok=True)
        agents_skills.mkdir(parents=True, exist_ok=True)

        # Shorthand alias mapping for ultra-smooth slash command UX
        aliases = {
            "diagnostic-assessment": "diagnostic",
            "quiz-learner": "quiz",
            "mock-exam": "mock",
            "flashcard-review": "flashcards",
            "review-progress": "progress",
            "scenario-drill": "scenario",
            "teach-topic": "teach",
        }

        skills_src = TEMPLATES_DIR / "skills"
        if skills_src.is_dir():
            for skill_dir in sorted(skills_src.glob("*")):
                if skill_dir.is_dir():
                    # Deploy to both .gemini/skills and .agents/skills
                    for target_root in (gemini_skills, agents_skills):
                        dest_skill_dir = target_root / skill_dir.name
                        dest_skill_dir.mkdir(parents=True, exist_ok=True)
                        for file in skill_dir.glob("*"):
                            dest_file = dest_skill_dir / file.name
                            shutil.copy2(file, dest_file)
                            created.append(dest_file)

                    # Also install shorthand slash command alias in .agents/skills/
                    if skill_dir.name in aliases:
                        alias_name = aliases[skill_dir.name]
                        alias_dir = agents_skills / alias_name
                        alias_dir.mkdir(parents=True, exist_ok=True)
                        for file in skill_dir.glob("*"):
                            shutil.copy2(file, alias_dir / file.name)

        # 4. Create .agents/skills.json to register skills explicitly
        skills_json_path = workspace_root / ".agents" / "skills.json"
        skills_json_data = {
            "entries": [
                {"path": ".agents/skills"},
                {"path": ".gemini/skills"},
            ]
        }
        skills_json_path.write_text(json.dumps(skills_json_data, indent=2) + "\n", encoding="utf-8")
        created.append(skills_json_path)

        # 5. MCP Configurations: mcp_config.json (Antigravity) & mcp.json (Universal/Kiro)
        workspace_server_py = (workspace_root / "study-memory-mcp" / "server.py").resolve()
        if workspace_server_py.is_file():
            server_py = workspace_server_py
        else:
            server_py = (TEMPLATES_DIR / "study-memory-mcp" / "server.py").resolve()

        server_entry = {
            "command": "python3",
            "args": [str(server_py)],
            "env": {
                "STUDY_MEMORY_DB": str(db_path.resolve()),
                "PYTHONUNBUFFERED": "1",
            },
        }

        # 5a. mcp_config.json (Native Antigravity format)
        mcp_config_path = workspace_root / "mcp_config.json"
        mcp_config_data: dict = {"mcpServers": {}}
        if mcp_config_path.is_file():
            try:
                mcp_config_data = json.loads(mcp_config_path.read_text(encoding="utf-8"))
            except Exception:
                mcp_config_data = {"mcpServers": {}}
        mcp_config_data.setdefault("mcpServers", {})["study-memory"] = server_entry
        mcp_config_path.write_text(json.dumps(mcp_config_data, indent=2) + "\n", encoding="utf-8")
        created.append(mcp_config_path)

        # 5b. mcp.json (Kiro / Cross-agent format)
        mcp_json_path = workspace_root / "mcp.json"
        mcp_json_data: dict = {"mcpServers": {}}
        if mcp_json_path.is_file():
            try:
                mcp_json_data = json.loads(mcp_json_path.read_text(encoding="utf-8"))
            except Exception:
                mcp_json_data = {"mcpServers": {}}
        mcp_json_data.setdefault("mcpServers", {})["study-memory"] = server_entry
        mcp_json_path.write_text(json.dumps(mcp_json_data, indent=2) + "\n", encoding="utf-8")
        created.append(mcp_json_path)

        return created

    def is_configured(self, workspace_root: Path) -> bool:
        return (
            (workspace_root / "GEMINI.md").is_file()
            or (workspace_root / ".gemini" / "rules").is_dir()
            or (workspace_root / ".agents" / "skills").is_dir()
        )

    def get_instructions(self, workspace_root: Path) -> str:
        return (
            "Agy CLI (Antigravity) Setup:\n"
            f"  1. In terminal, navigate to: cd {workspace_root}\n"
            "  2. Launch Antigravity: agy\n"
            "  3. Available Slash Commands:\n"
            "     - /diagnostic (or /diagnostic-assessment): 14-task baseline\n"
            "     - /quiz (or /quiz-learner): Adaptive topic practice\n"
            "     - /mock (or /mock-exam): 20Q mini or 65Q full mock\n"
            "     - /flashcards (or /flashcard-review): Active recall drill\n"
            "     - /progress (or /review-progress): Knowledge mastery report\n"
            "     - /teach (or /teach-topic): Concept deep-dive & trade-offs\n"
            "     - /scenario (or /scenario-drill): Architecture trade-off design\n"
            "  4. Try asking: 'Start an adaptive study plan for learner miguel'"
        )
