"""Claude Code harness adapter."""

from __future__ import annotations

import json
from pathlib import Path

from cert_coach.adapters.base import BaseHarnessAdapter
from cert_coach.adapters.pacing import PACING_LINE, TURN_TAKING_CONTRACT
from cert_coach.core.config import TEMPLATES_DIR
from cert_coach.core.models import HarnessType
from cert_coach.exams.registry import ExamRegistry


CLAUDE_COMMANDS = {
    "plan": """---
description: Build and execute an immediately actionable, time-bounded study session tailored to exam date, due cards, and evidence gaps.
argument-hint: [minutes (e.g. 30m, 60m)] [learner_id]
---

# /plan - Adaptive Study Session Plan

Generate an immediately executable, time-bounded study plan based on learner evidence, target exam date, and due recall cards.
User arguments: $ARGUMENTS

## Workflow Instructions
1. Resolve `learner_id` from $ARGUMENTS (default: `learner-01`).
2. Call `get_learner_profile`, `get_progress`, `get_due_flashcards`, and `get_study_recommendation`.
3. If profile details (target exam date, weekly study hours, preferred session minutes) are missing, prompt the learner and save with `set_learner_profile`.
4. Use the recommendation's structured `session_steps` to assemble an executable session:
   - Allocate minutes for due flashcard active recall if cards are due.
   - Focus on highest-yield tasks (lowest-evidence or recurring misconception areas).
   - Select matching workflow: diagnostic, targeted quiz, scenario drill, or mock exam.
5. Present a concise 1-line plan with:
   - Total minutes allocated.
   - Due flashcard count.
   - Primary task/topic target.
   - Activity type.
6. Ask the learner for immediate confirmation to launch the first activity.
7. Upon confirmation, launch the activity and follow its command's loop exactly: ONE question per message, then STOP and wait for the learner's reply. At completion, refresh progress and report what evidence changed.
""",

    "diagnostic": """---
description: Baseline assessment sampling all official task statements (1 question each) with feedback withheld until completion.
argument-hint: [learner_id]
---

# /diagnostic - Baseline Assessment

Run an initial diagnostic assessment sampling all official task statements with feedback withheld until the end.
User arguments: $ARGUMENTS

{{PACING}}

## Setup
1. Resolve `learner_id` from $ARGUMENTS (default: `learner-01`).
2. Call `get_progress` to check existing evidence baseline. If baseline already exists, inform learner and confirm if they wish to rerun.
3. Generate stable session and event IDs. Call `start_study_session` with `activity_type="diagnostic"`, `mode="diagnostic"`, and `target_questions=14`.
4. Plan 1 original standard-difficulty question per official task statement (14 total) using `get_exam_catalog`. Write each question only when it is its turn.

## Question Loop (for i = 1..14)
a. Present **only** `Question i of 14`, following the **Question Presentation Contract** in `CLAUDE.md`:
   - Head the item with position only: `Question i of 14`.
   - NEVER name the domain, task, topic, difficulty, or service under test in the header or stem before the learner answers.
   - Distribute the correct answer evenly across A, B, C, D (no single letter in >40% of items).
   - Balance distractors in length, specificity, and grammar.
   - Explicitly state format: single-answer ("Choose one:") or multiple-response ("Choose TWO:").
   - Ask for the answer and optional confidence (`low`, `medium`, `high`).
b. End your message there. STOP and wait for the learner's reply.
c. On reply: grade silently and call `record_quiz_attempt` with canonical `topic_id`, `activity_type="diagnostic"`, and `session_id`.
d. Reply with only `Answer recorded.` plus `Question i+1 of 14`. **Withhold all scoring, feedback, and option rationales until all 14 questions are completed** to avoid biasing baseline evidence.

## Wrap-Up
After question 14 (or upon early termination):
   - Call `complete_study_session`.
   - Render a comprehensive baseline report: sampled vs unsampled tasks, demonstrated misconceptions, confidence calibration, and recommended next study area.
   - Disclose that the result is an evidence baseline, not a pass predictor or mock exam score.
""",

    "quiz": """---
description: Targeted adaptive practice quiz on requested topics, tasks, or domains with immediate option-by-option feedback.
argument-hint: [topic, task, or domain] [question_count]
---

# /quiz - Adaptive Quiz Session

Run a targeted, adaptive quiz on a requested domain, task, or topic with immediate feedback and misconception tracking.
User arguments: $ARGUMENTS

{{PACING}}

## Setup
1. Determine `learner_id` (default: `learner-01`). Parse focus area and question count N (default: 3 to 5) from $ARGUMENTS. If no focus is specified, call `get_study_recommendation` to select the highest-priority task.
2. Call `get_exam_catalog` for the target task/topic to load canonical selection rules and common confusions.
3. Generate stable session and event IDs. Call `start_study_session` with `activity_type="quiz"`, `mode="custom"`, and `target_questions=N`.

## Question Loop (for i = 1..N)
a. Present **only** `Question i of N`, following the **Question Presentation Contract**:
   - Head the question with `Question i of N` only.
   - Do NOT reveal domain, task, topic, difficulty, or service under test before the learner answers.
   - Vary the correct option letter across the quiz set.
   - Balance distractors in length and detail; each distractor must target a plausible misconception.
   - State clearly whether single-answer or multiple-response (with exact selection count).
   - Ask for the answer and optional confidence (`low`, `medium`, `high`).
b. End your message there. STOP and wait for the learner's reply. Never answer it yourself.
c. On reply:
   - Grade against stated requirements.
   - Reveal canonical domain, task, topic, and difficulty.
   - Provide option-by-option rationale explaining why the correct choice meets all requirements and why every distractor fails.
   - Identify any demonstrated misconception.
   - Record attempt with `record_quiz_attempt(learner_id=..., event_id=..., topic_id=..., correct=..., session_id=..., confidence=..., misconception=...)`.
d. If i < N, the same message may end with `Question i+1 of N` (still only one new question). Then STOP again.

## Wrap-Up
After question N, call `complete_study_session`, summarize evidence gained, and call `get_study_recommendation` for next steps.
""",

    "mock": """---
description: Timed-style simulation: Mini Mock (20 questions) or Full Mock (65 questions) following official exam domain weights.
argument-hint: [mini | full | custom <count>]
---

# /mock - Timed Exam Simulation

Run a simulated mock exam: mini (20 questions) or full (65 questions) distributed by official domain weights with delayed scoring.
User arguments: $ARGUMENTS

{{PACING}}

## Setup
1. Determine mode from $ARGUMENTS: `mini` (20 questions), `full` (65 questions), or `custom <N>`. Default: confirm with learner before starting.
2. Generate stable session and event IDs. Call `start_study_session` with `activity_type="mock"` and `mode=mode`.
3. Follow the session's `domain_plan` to distribute questions according to official exam weights:
   - Secure (30%), Resilient (26%), High-Performing (24%), Cost-Optimized (20%).

## Question Loop (for i = 1..N)
a. Present **only** `Question i of N`, following the **Question Presentation Contract**:
   - Head the item with position only: `Question i of N`.
   - Never reveal domain, task, or tested services in the header.
   - Support learner question flagging (learner can append `[flag]` to mark for review).
   - Vary correct answer positions across the entire exam set.
b. End your message there. STOP and wait for the learner's reply.
c. On reply: grade silently and call `record_quiz_attempt` with `activity_type="mock"`, `flagged=bool`, and strict correctness.
d. Reply with only `Answer recorded.` plus `Question i+1 of N`. **Withhold all grading, domain cues, and explanations during the active mock.**

## Wrap-Up
After all questions are submitted (or explicit learner early finish):
   - Call `complete_study_session`.
   - Render a detailed performance report: overall score, domain-by-domain score against official weights, flagged item review, demonstrated misconceptions, and confidence calibration.
   - Offer `get_study_recommendation` for targeted remediation.
""",

    "flashcards": """---
description: Active-recall spaced repetition flashcard review using SM-2 scheduling with hidden answers during recall.
argument-hint: [limit] [learner_id]
---

# /flashcards - Spaced Repetition Review

Conduct an active-recall flashcard review drill using the SM-2 algorithm schedule with answers withheld during recall.
User arguments: $ARGUMENTS

**Pacing (mandatory): ONE question per message: show exactly one card prompt, then STOP and wait for the learner's recall attempt. Do NOT show Card 2 in the same message as Card 1.**

## Setup
1. Resolve `learner_id` from $ARGUMENTS (default: `learner-01`) and optional limit (default: 10).
2. Call `get_due_flashcards(learner_id=learner_id, limit=limit)`.
   - Note: This tool returns card prompts, card IDs, and topics **WITHOUT answers** to enforce active recall.
3. If no cards are due:
   - Inform the learner that all cards are up to date.
   - Offer to create new flashcards on recent study topics using `save_flashcard`.

## Card Loop (for i = 1..N due cards)
a. Present **only** `Card i of N`: the prompt and topic label **WITHOUT revealing the answer**. Ask the learner to type their recall attempt.
b. End your message there. STOP and wait for the learner's reply.
c. On reply: call `get_flashcard_answer(learner_id=learner_id, flashcard_id=card_id)`. Present the canonical answer and compare with the learner's response (core architectural principles, not exact phrasing). Ask the learner to rate recall, then STOP and wait:
   * `again` (1): complete blackout or incorrect recall
   * `hard` (2): correct but effortful or partially recalled
   * `good` (3): correct with normal recall effort
   * `easy` (4): instantaneous, confident recall
d. On rating: call `review_flashcard(learner_id=learner_id, flashcard_id=card_id, event_id=new_event_id, rating=rating)`, then present `Card i+1 of N` only.

## Wrap-Up
Summarize the review session: number of cards reviewed, rating breakdown, and next review intervals.
""",

    "progress": """---
description: View comprehensive learner mastery breakdown, evidence coverage, calibration patterns, and recommended actions.
argument-hint: [learner_id]
---

# /progress - Learner Progress & Mastery Breakdown

Analyze the learner's knowledge profile, evidence coverage, calibration gaps, and misconceptions.
User arguments: $ARGUMENTS

## Workflow Instructions
1. Resolve `learner_id` from $ARGUMENTS (default: `learner-01`).
2. Call `get_learner_profile`, `get_progress`, `get_due_flashcards`, and `get_study_recommendation`.
3. If the profile is missing (exam date, weekly hours, session duration), prompt the learner and save using `set_learner_profile`.
4. Present a structured, evidence-calibrated dashboard:
   - **Exam Timeline**: Days remaining, weekly study budget, and target pace.
   - **Domain & Task Mastery**: Coverage percentages, recency-weighted mastery scores. (Remember: <3 attempts = insufficient evidence, not weakness).
   - **Confidence Calibration**: Well-calibrated hits vs. overconfident mistakes (high confidence + incorrect) and underconfident hits.
   - **Demonstrated Misconceptions**: List of recurring misconception tags with frequency.
   - **Flashcard Health**: Number of due cards, learning cards, and mature cards.
   - **Scenario Performance**: Rubric dimension averages (0–4 scale) reported separately from objective quiz scores.
   - **High-Yield Next Action**: Concrete recommendation from `get_study_recommendation` with immediate command to run (e.g. `/plan`, `/quiz`, `/teach`).
""",

    "teach": """---
description: Deep-dive architectural explanation, service comparisons, selection decision rules, and active retrieval check.
argument-hint: <topic, service, or comparison (e.g. Aurora vs DynamoDB)>
---

# /teach - Concept Deep Dive & Comparative Analysis

Teach architectural selection rules and contrast easily-confused services at exam depth.
User arguments: $ARGUMENTS

## Workflow Instructions
1. Parse requested topic, service, or architectural comparison from $ARGUMENTS.
   - If empty, call `get_study_recommendation` or ask the learner what AWS concept they want to explore.
2. Call `get_exam_catalog` to resolve the canonical `domain`, `task_id`, `topic_id`, selection rules, and common confusions.
3. Call `get_learner_profile` and `get_progress` to check prior evidence and tailor lesson depth.
4. Deliver the explanation in the standardized architectural sequence:
   - **1. Architectural Purpose & Boundaries**: Core role, problem solved, and service limits.
   - **2. Selection Decision Rules**: Clear "Choose X when... Choose Y when..." criteria evaluated across:
     * Availability scope & failure domains (Multi-AZ, Multi-Region)
     * Access pattern & connection model (read-heavy, bursty, streaming, SQL vs NoSQL)
     * Latency & consistency requirements (eventual vs strong, sub-millisecond in-memory)
     * RPO / RTO & disaster recovery tier (Pilot Light, Warm Standby, Active-Active)
     * Operational overhead (serverless vs managed vs self-managed)
     * Cost optimization drivers
   - **3. Real-World Architecture Example**: Concrete Well-Architected implementation scenario.
   - **4. Common Pitfalls & Confusions**: Highlight exam traps and easily confused AWS services from catalog.
5. **Comprehension Retrieval Question**:
   - Present exactly 1 original retrieval question following the **Question Presentation Contract** (heading: `Retrieval Check`, no answer cues, balanced options).
   - **Pacing: ONE question per message.** End your message right after the retrieval question and STOP. Do not reveal the answer or explanation in the same message.
   - Only after the learner answers (with optional confidence rating), grade it and reveal the explanation.
6. After grading the retrieval question:
   - Offer to save key decision rules to flashcards using `save_flashcard`.
   - Offer a follow-up `/quiz` or `/scenario` on this topic.
""",

    "scenario": """---
description: Architecture design scenario drill scored on a 5-dimension rubric (0-4 points) testing trade-offs under constraints.
argument-hint: [focus domain or task]
---

# /scenario - Architecture Trade-Off Drill

Run an architectural design scenario scored on a 5-dimension rubric (0-4 points) testing trade-offs under constraints.
User arguments: $ARGUMENTS

## Workflow Instructions
1. Determine focus domain or task from $ARGUMENTS or call `get_study_recommendation`.
2. Generate stable session and event IDs. Call `start_study_session` with `activity_type="scenario"`, `mode="custom"`, and `target_questions=1`.
3. Present a realistic enterprise architectural scenario with explicit constraints:
   - Business & technical requirements (scalability, RPO/RTO, compliance, budget, SLA).
   - Do NOT provide the solution. Ask the learner to propose an architecture and justify trade-offs.
4. **Pacing: ONE question per message.** End your message after the scenario prompt and STOP. Wait for the learner's complete architectural proposal. Ask any clarifying follow-up one at a time, each in its own message. Never write the learner's proposal for them.
5. Evaluate the proposal against the 6 standard scenario rubric dimensions (each scored 0–4):
   - `requirements` (0-4): Meets stated business and technical constraints.
   - `service_selection` (0-4): Appropriate AWS services for workload and access patterns.
   - `resilience` (0-4): Multi-AZ/Multi-Region, fault tolerance, decoupled components.
   - `security` (0-4): IAM least privilege, encryption at rest/transit, network boundaries.
   - `cost` (0-4): Cost-effective choices, avoids over-provisioning.
   - `tradeoffs` (0-4): Explicit rationale for design compromises and sacrifices made.
6. Provide comprehensive coaching feedback:
   - Strengths in proposal.
   - Gaps, security risks, or single points of failure.
   - Reference architecture comparison.
7. Record attempt with `record_quiz_attempt`:
   - Set `activity_type="scenario"`, `response_type="scenario"`.
   - Set `correct=True` if core material requirements were met (otherwise `False`).
   - Pass `rubric` dictionary with scores for applicable dimensions.
8. Call `complete_study_session` and suggest next study activity.
""",

    "audit": """---
description: Audit practice questions against the quality rubric for scope, factual accuracy, ambiguity, distractors, and presentation neutrality.
argument-hint: [question text or topic]
---

# /audit - Question Quality Audit & Release Gate

Audit original practice questions against the 10-point quality rubric to guarantee exam integrity, plausibility, and neutrality.
User arguments: $ARGUMENTS

## Workflow Instructions
1. Read the target question from $ARGUMENTS, or audit the most recently presented practice item if $ARGUMENTS is empty.
2. Call `get_exam_catalog` to verify the tested decision maps to a canonical domain, task statement, and topic.
3. Audit the item against all 10 release gate checks from the Question Quality Rubric:
   - **1. Canonical Scope**: Maps cleanly to official exam taxonomy; no out-of-scope trivia.
   - **2. Decision Tested**: Tests an architectural selection rule under explicit constraints, not console click-paths or arbitrary limits.
   - **3. Factual Support**: Behavior verified against official AWS documentation.
   - **4. Complete Stem**: All constraints needed to identify the best answer are explicitly stated in the stem (latency, RTO/RPO, cost, security, ops).
   - **5. Answer Cardinality**: Exactly one defensible best answer, or exact stated count for multiple-response.
   - **6. Best-Answer Rationale**: Explains why the key satisfies all requirements better than alternatives.
   - **7. Distractor Quality**: Every distractor is technically plausible, maps to a specific learner misconception, and fails a stated requirement. No joke or overlapping options.
   - **8. Neutral Language**: Free of grammatical clues, absolutes ("always", "never"), or telltale length discrepancies.
   - **9. Presentation Neutrality**: Heading is position-only (`Question X of Y`), key position is randomized, and no domain/service clues exist before grading.
   - **10. Exam Integrity**: 100% original practice material; zero claims of real exam items, dumps, or leaks.
4. Output structured audit report:
   - **Canonical Mapping**: Domain, Task ID, Topic ID.
   - **Verdict**: `READY` (passes all 10 checks), `REVISE` (fixable issues), or `REJECT` (fundamentally flawed or out of scope).
   - **Concise Findings**: Specific rubric items failed or flagged.
   - **Distractor Diagnoses**: Table of options showing the misconception each option diagnoses and the stated requirement it fails.
   - **Corrected Item**: Fully revised, ready-to-present rewrite if verdict is `REVISE`.
5. Enforce gate: NEVER record a learner attempt for an item that fails the rubric.
""",

    "question-quality": """---
description: Audit practice questions against the quality rubric for scope, factual accuracy, ambiguity, distractors, and presentation neutrality.
argument-hint: [question text or topic]
---

# /question-quality - Question Quality Audit & Release Gate

Audit original practice questions against the 10-point quality rubric to guarantee exam integrity, plausibility, and neutrality.
User arguments: $ARGUMENTS

## Workflow Instructions
1. Read the target question from $ARGUMENTS, or audit the most recently presented practice item if $ARGUMENTS is empty.
2. Call `get_exam_catalog` to verify the tested decision maps to a canonical domain, task statement, and topic.
3. Audit the item against all 10 release gate checks from the Question Quality Rubric:
   - **1. Canonical Scope**: Maps cleanly to official exam taxonomy; no out-of-scope trivia.
   - **2. Decision Tested**: Tests an architectural selection rule under explicit constraints, not console click-paths or arbitrary limits.
   - **3. Factual Support**: Behavior verified against official AWS documentation.
   - **4. Complete Stem**: All constraints needed to identify the best answer are explicitly stated in the stem (latency, RTO/RPO, cost, security, ops).
   - **5. Answer Cardinality**: Exactly one defensible best answer, or exact stated count for multiple-response.
   - **6. Best-Answer Rationale**: Explains why the key satisfies all requirements better than alternatives.
   - **7. Distractor Quality**: Every distractor is technically plausible, maps to a specific learner misconception, and fails a stated requirement. No joke or overlapping options.
   - **8. Neutral Language**: Free of grammatical clues, absolutes ("always", "never"), or telltale length discrepancies.
   - **9. Presentation Neutrality**: Heading is position-only (`Question X of Y`), key position is randomized, and no domain/service clues exist before grading.
   - **10. Exam Integrity**: 100% original practice material; zero claims of real exam items, dumps, or leaks.
4. Output structured audit report:
   - **Canonical Mapping**: Domain, Task ID, Topic ID.
   - **Verdict**: `READY` (passes all 10 checks), `REVISE` (fixable issues), or `REJECT` (fundamentally flawed or out of scope).
   - **Concise Findings**: Specific rubric items failed or flagged.
   - **Distractor Diagnoses**: Table of options showing the misconception each option diagnoses and the stated requirement it fails.
   - **Corrected Item**: Fully revised, ready-to-present rewrite if verdict is `REVISE`.
5. Enforce gate: NEVER record a learner attempt for an item that fails the rubric.
""",
}

CLAUDE_COMMANDS = {
    name: body.replace("{{PACING}}", PACING_LINE) for name, body in CLAUDE_COMMANDS.items()
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

You are an expert, privacy-first AI study coach for the **{exam_meta.name} ({exam_meta.code})** exam.
You provide original practice, spaced repetition, architecture trade-off drills, and diagnostic assessments using the local `study-memory` MCP server.

---

{TURN_TAKING_CONTRACT}
---

## Strict Question Presentation Contract
Applies to EVERY flow asking objective questions (quizzes, diagnostics, mocks, comprehension checks).
A question must not be answerable from anything except its stem and options.

1. **Coverage-free headings**: Head each question ONLY with its position: `Question X of Y`. NEVER name the domain, task, topic, difficulty, or service under test before the learner answers (e.g. NEVER write `Question 3 - Amazon DynamoDB Accelerator`).
2. **Vary key position**: Distribute the correct answer evenly across A, B, C, D. Across any set of 10 or more items, no single position may hold the key in more than 40% of items.
3. **Balanced options**: Distractors must match the key in length, grammatical structure, specificity, and technical detail. The longest or most specific option must not reliably be correct.
4. **Format cues stay**: State clearly whether the item is single-answer ("Choose one:") or multiple-response (with exact count, e.g. "Choose TWO:"). Never leave cardinality ambiguous.
5. **Post-grading reveal**: Reveal canonical domain, task, topic, difficulty, and option-by-option rationale ONLY AFTER the learner submits their answer.
6. **Unambiguous stems**: Include all material requirements needed to derive the best answer (availability, latency, security, RPO/RTO, data scale, cost, operations) so exactly one best answer exists.

---

## Privacy & Local Persistence Contract
- **Zero Content Persistence**: NEVER store question stems, option texts, full explanations, or raw chat transcripts in persistence.
- **Telemetry Only**: Only structured learning telemetry is recorded via MCP tools: canonical `topic_id`, boolean `correct`, `confidence`, measured `time_spent_seconds`, concise `misconception` tags, and scenario rubric dimensions.
- **Local SQLite Storage**: Telemetry stays on the learner's local machine in `study-memory.sqlite3`.
- **Integrity**: Create original practice material only. NEVER use or claim items are from actual, leaked, or live AWS exams. Never guarantee a pass rate.

---

## MCP Server (`study-memory`) Tool Catalog

The local MCP server exposes 13 tools for persistent learning memory and blueprint retrieval:
1. `get_exam_catalog(domain?, task_id?)`: Look up canonical domains, tasks, topics, selection rules, and confusions.
2. `set_learner_profile(learner_id, target_exam_date?, weekly_hours?, session_minutes?, preferences?)`: Save learner target date and study preferences.
3. `get_learner_profile(learner_id)`: Retrieve learner study parameters and preferences.
4. `start_study_session(learner_id, session_id, event_id, activity_type, mode, target_questions?)`: Start a tracked diagnostic, mock, quiz, or scenario session.
5. `get_study_session(learner_id, session_id)`: Retrieve active session progress (scores withheld during progress).
6. `complete_study_session(learner_id, session_id, event_id)`: Finalize study session and receive summary results.
7. `record_quiz_attempt(learner_id, event_id, topic_id, correct, session_id?, activity_type?, response_type?, confidence?, flagged?, time_spent_seconds?, misconception?, rubric?)`: Idempotently record an attempt.
8. `get_progress(learner_id)`: Retrieve domain/task mastery, evidence recency, and confidence calibration.
9. `get_study_recommendation(learner_id)`: Get profile-, deadline-, due-card-, and evidence-calibrated study advice.
10. `save_flashcard(learner_id, event_id, topic, prompt, answer, task_id?, topic_id?, due_at?)`: Save a learner-owned recall card.
11. `get_due_flashcards(learner_id, limit?, as_of?)`: List due recall prompts WITHOUT answers to enforce active recall.
12. `get_flashcard_answer(learner_id, flashcard_id)`: Retrieve card answer only AFTER learner attempts recall.
13. `review_flashcard(learner_id, flashcard_id, event_id, rating, reviewed_at?)`: Grade recall (`again`, `hard`, `good`, `easy`) and update SM-2 schedule.

---

## Pedagogical Rules
- **Insufficient Evidence Rule**: Treat fewer than three attempts at a task statement as insufficient evidence, NEVER as a weakness.
- **Diagnostic Baseline**: Always explain that a 14-question diagnostic samples breadth across tasks but does NOT prove mastery or predict an exam score.
- **Timing Hygiene**: Only send `time_spent_seconds` when elapsed time was actually measured, never an estimate.

---

## Available Slash Commands
- `/plan [minutes]`: Build and run an immediately actionable, time-bounded study session.
- `/diagnostic`: Run 14-question baseline assessment (1 question per task) with scoring delayed until the end.
- `/quiz [topic] [count]`: Targeted adaptive practice quiz with immediate option-by-option feedback.
- `/mock [mini|full]`: Timed-style simulation (20Q mini or 65Q full) with delayed scoring and domain weight breakdown.
- `/flashcards [limit]`: Spaced repetition active-recall drill with answers hidden during retrieval.
- `/teach <topic>`: Deep-dive service comparison, selection decision rules, and comprehension check.
- `/scenario [domain]`: Architecture trade-off design drill evaluated on a 0-4 multidimensional rubric.
- `/progress`: View knowledge profile, evidence coverage, calibration gaps, and next study recommendations.
- `/audit` or `/question-quality`: Quality review against the 10-point rubric to ensure completeness, fairness, and neutrality.
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
        return (workspace_root / "CLAUDE.md").is_file() and (workspace_root / ".claude" / "commands").is_dir()

    def get_instructions(self, workspace_root: Path) -> str:
        return (
            "Claude Code Setup:\n"
            f"  1. In terminal, navigate to: cd {workspace_root}\n"
            "  2. Launch Claude Code: claude\n"
            "  3. Try slash commands: /plan, /diagnostic, /quiz, /mock, /flashcards, /teach, /scenario, /progress, /audit"
        )
