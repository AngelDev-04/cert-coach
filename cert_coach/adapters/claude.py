"""Claude Code harness adapter."""

from __future__ import annotations

import json
from pathlib import Path

from cert_coach.adapters.base import BaseHarnessAdapter
from cert_coach.core.config import TEMPLATES_DIR
from cert_coach.core.models import HarnessType
from cert_coach.exams.registry import ExamRegistry


CLAUDE_COMMANDS = {
    "diagnostic": """# /diagnostic - Baseline Assessment

Run an initial diagnostic assessment sampling all official task statements with feedback withheld until the end.

## Instructions
1. Check or ask for non-sensitive `learner_id` (default: `learner-01`).
2. Call MCP `get_progress` to see existing baseline.
3. Call MCP `start_study_session` with `activity_type="diagnostic"`.
4. Ask exactly 1 question per official task statement.
5. Strictly adhere to the **Question Presentation Contract** in `CLAUDE.md`:
   - Head items with position only (`Question 1 of 14`).
   - Do NOT name domain or service in the question header.
   - Balance distractors in length and detail.
   - Withhold feedback and scoring until all 14 questions are answered.
6. After completion, record each attempt with `record_quiz_attempt`, call `complete_study_session`, and render a summary report.
""",
    "quiz": """# /quiz - Adaptive Quiz Session

Run a targeted, adaptive quiz on a requested domain, task, or topic.

## Instructions
1. Determine `learner_id` and the requested focus area (or call `get_study_recommendation`).
2. Call `get_exam_catalog` for the target task to load canonical rules and common confusions.
3. Call `start_study_session` with `activity_type="quiz"`.
4. Present original questions one by one according to the **Question Presentation Contract**:
   - Head each question with `Question X of Y`.
   - Never give away the domain, task, or service before the learner answers.
   - Require low/medium/high confidence level when appropriate.
5. After the learner answers:
   - Grade against requirements and explain option-by-option rationale.
   - Record attempt with `record_quiz_attempt` using canonical `topic_id`.
6. Call `complete_study_session` at end of quiz and offer next study step.
""",
    "mock": """# /mock - Timed Exam Simulation

Run a simulated mock exam: mini (20 questions) or full (65 questions) following official domain weights.

## Instructions
1. Confirm format: Mini Mock (20 questions) or Full Mock (65 questions).
2. Call `start_study_session` with `activity_type="mock"`, `mode="mini"` or `mode="full"`.
3. Present questions one at a time with flagging support.
4. Withhold all grading, domain hints, and explanations until the mock concludes.
5. After all items are submitted:
   - Grade all questions and record with `record_quiz_attempt`.
   - Call `complete_study_session`.
   - Break down results by domain against official exam weights.
""",
    "flashcards": """# /flashcards - Spaced Repetition Review

Conduct an active-recall flashcard review drill using the SM-2 algorithm schedule.

## Instructions
1. Call `review_flashcards` with `action="list_due"` for the learner.
2. If due cards exist, present each card prompt **WITHOUT** showing the answer.
3. Wait for learner to recall mentally or articulate their answer.
4. Reveal the canonical answer and ask the learner to rate their recall:
   - `Again` (1)
   - `Hard` (2)
   - `Good` (3)
   - `Easy` (4)
5. Call `review_flashcards` with `action="record_review"` and the selected rating.
""",
    "progress": """# /progress - Learner Progress & Mastery Breakdown

Analyze the learner's knowledge profile, evidence coverage, and misconceptions.

## Instructions
1. Call `get_progress` for the active `learner_id`.
2. Call `get_study_recommendation` to find lowest-evidence or high-misconception tasks.
3. Present a structured dashboard:
   - Coverage by domain (percentage of topics attempted).
   - Demonstrated misconceptions and recurrence count.
   - Spaced recall card counts (due, learned, new).
   - High-yield recommended next action.
""",
    "teach": """# /teach - Concept Deep Dive & Comparative Analysis

Teach architectural selection rules and contrast easily-confused services.

## Instructions
1. For the requested topic or task, call `get_exam_catalog`.
2. Present:
   - Core architectural purpose and service boundaries.
   - Selection Decision Rules (When to choose X over Y).
   - Common Exam Pitfalls & Confusions.
3. Conclude with one active retrieval scenario question to verify comprehension before recording.
""",
    "scenario": """# /scenario - Architecture Trade-Off Drill

Run an architectural design scenario scored on a 5-dimension rubric (0-4 points).

## Instructions
1. Provide a realistic scenario with explicit constraints (budget, RPO/RTO, compliance, scale).
2. Ask the learner to propose an end-to-end architecture and justify trade-offs.
3. Evaluate the proposal against the 5 rubric dimensions:
   - Requirements Alignment (0-4)
   - Security Controls (0-4)
   - Resilience & Reliability (0-4)
   - Cost Efficiency (0-4)
   - Explicit Trade-off Rationale (0-4)
4. Record with `record_scenario_attempt` including rubric scores and feedback.
""",
}


class ClaudeCodeAdapter(BaseHarnessAdapter):
    """Generates Claude Code configuration (CLAUDE.md, .claude/commands/, .mcp.json)."""

    @property
    def harness_type(self) -> HarnessType:
        return HarnessType.CLAUDE

    @property
    def display_name(self) -> str:
        return "Claude Code"

    @property
    def description(self) -> str:
        return "Installs Claude Code slash commands (.claude/commands/), CLAUDE.md rules, and MCP wiring."

    def generate(
        self,
        workspace_root: Path,
        exam: str,
        db_path: Path,
        mcp_launch_cmd: list[str] | None = None,
    ) -> list[Path]:
        created: list[Path] = []
        exam_meta = ExamRegistry.get_metadata(exam)

        # 1. CLAUDE.md
        claude_md_path = workspace_root / "CLAUDE.md"
        claude_md_content = f"""# {exam_meta.name} ({exam_meta.code}) Study Coach - Claude Code Instructions

You are an expert, privacy-first study coach for the **{exam_meta.name} ({exam_meta.code})** exam.
You provide original practice, spaced repetition, scenario drills, and diagnostics using the local `study-memory` MCP server.

## Strict Question Presentation Contract
Applies to EVERY flow asking objective questions (quizzes, diagnostics, mocks):
1. **Coverage-free headings**: Head each question ONLY with its position: `Question X of Y`. NEVER name the domain, task, topic, difficulty, or service under test before the learner answers.
2. **Vary key position**: Distribute the correct answer evenly across A, B, C, D. No single position should hold the key in more than 40% of items.
3. **Balanced options**: Distractors must match the key in length, grammar, and technical detail. The longest option must not be reliably correct.
4. **Format cues**: State whether the question is single-answer or multiple-response (and how many to choose).
5. **Post-grading reveal**: Reveal canonical topic, domain, difficulty, and option rationales ONLY AFTER the learner submits their answer.

## Privacy & Persistence Contract
- Never store question stems, option text, or transcripts in SQLite.
- Only record structured telemetry: canonical topic_id, correctness (bool), confidence, and concise misconception tags.
- Always use the tools provided by the `study-memory` MCP server.

## Available Slash Commands
- `/diagnostic`: Run baseline 14-question assessment across all official tasks.
- `/quiz`: Adaptive practice quiz on requested topics with immediate feedback.
- `/mock`: Mini (20Q) or Full (65Q) mock exam with delayed scoring.
- `/flashcards`: Spaced repetition recall review.
- `/progress`: View mastery breakdown and study recommendations.
- `/teach`: Deep-dive service comparison and trade-off rules.
- `/scenario`: Architectural design scenario scored on 0-4 rubric.
"""
        claude_md_path.write_text(claude_md_content, encoding="utf-8")
        created.append(claude_md_path)

        # 2. .claude/commands/
        commands_dir = workspace_root / ".claude" / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)

        for cmd_name, cmd_content in CLAUDE_COMMANDS.items():
            cmd_file = commands_dir / f"{cmd_name}.md"
            cmd_file.write_text(cmd_content, encoding="utf-8")
            created.append(cmd_file)

        # 3. .mcp.json (for Claude Code project-level MCP registration)
        workspace_server_py = (workspace_root / "study-memory-mcp" / "server.py").resolve()
        if workspace_server_py.is_file():
            server_py = workspace_server_py
        else:
            server_py = (TEMPLATES_DIR / "study-memory-mcp" / "server.py").resolve()

        mcp_json_path = workspace_root / ".mcp.json"
        mcp_data = {
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

        return created

    def is_configured(self, workspace_root: Path) -> bool:
        return (workspace_root / "CLAUDE.md").is_file() and (workspace_root / ".claude" / "commands").is_dir()

    def get_instructions(self, workspace_root: Path) -> str:
        return (
            "Claude Code Setup:\n"
            f"  1. In terminal, navigate to: cd {workspace_root}\n"
            "  2. Launch Claude Code: claude\n"
            "  3. Try slash commands: /diagnostic, /quiz, /mock, /flashcards, /progress"
        )
