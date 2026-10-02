"""SQLite-backed local memory for the adaptive AWS SAA-C03 study coach."""

from __future__ import annotations

import json
import math
import os
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from catalog import DOMAINS, TASKS, TOPICS
from telemetry import Telemetry

POWER_VERSION = "0.3.0"
DIFFICULTIES = {"foundation", "standard", "challenging"}
OBJECTIVE_ACTIVITIES = {"quiz", "diagnostic", "mock"}
ACTIVITY_TYPES = OBJECTIVE_ACTIVITIES | {"scenario"}
RESPONSE_TYPES = {"single-answer", "multiple-response", "scenario"}
CONFIDENCE_LEVELS = {"low", "medium", "high"}
RUBRIC_DIMENSIONS = {"requirements", "service_selection", "resilience", "security", "cost", "tradeoffs"}
FLASHCARD_RATINGS = {"again", "hard", "good", "easy"}
ACTIVITY_ALIASES = {
    "diagnostic": "diagnostic",
    "diagnostic_assessment": "diagnostic",
    "diagnostic_session": "diagnostic",
    "baseline": "diagnostic",
    "mock": "mock",
    "mock_exam": "mock",
    "practice_exam": "mock",
    "quiz": "quiz",
    "quiz_learner": "quiz",
    "practice": "quiz",
    "targeted_practice": "quiz",
    "scenario": "scenario",
    "scenario_drill": "scenario",
}
RESPONSE_ALIASES = {
    "single_answer": "single-answer",
    "single": "single-answer",
    "multiple_choice": "single-answer",
    "multiple_response": "multiple-response",
    "multi_select": "multiple-response",
    "multiple_select": "multiple-response",
    "scenario": "scenario",
}
SCHEMA_VERSION = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


DEFAULT_DATABASE_PATH = Path.home() / ".kiro" / "aws-saa-study-coach" / "study-memory.sqlite3"


def default_database_path() -> Path:
    """Resolve the configured database path, ignoring host variables that were never expanded.

    An unexpanded ``${PLUGIN_DATA}`` would otherwise create a literal directory of
    that name under the launch cwd and silently strand the learner's history.
    """
    configured = os.environ.get("STUDY_MEMORY_DB") or os.environ.get("AWS_SAA_STUDY_DB")
    if not configured:
        return DEFAULT_DATABASE_PATH
    expanded = os.path.expandvars(configured)
    if "${" in expanded or expanded.startswith("$"):
        print(
            f"study-memory: ignoring configured database path={configured!r} (unexpanded variable); "
            f"using {DEFAULT_DATABASE_PATH}",
            file=sys.stderr,
        )
        return DEFAULT_DATABASE_PATH
    return Path(expanded).expanduser()


def _require_text(value: Any, name: str, *, maximum: int = 200) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    if len(normalized) > maximum:
        raise ValueError(f"{name} must be at most {maximum} characters")
    return normalized


def _optional_text(value: Any, name: str, *, maximum: int = 500) -> str | None:
    if value is None:
        return None
    return _require_text(value, name, maximum=maximum)


_TRUE_TOKENS = {"true", "t", "yes", "y", "1", "correct"}
_FALSE_TOKENS = {"false", "f", "no", "n", "0", "incorrect"}


def _coerce_bool(value: Any, name: str) -> bool:
    """Accept the boolean spellings a model actually emits, but never a guess."""
    if type(value) is bool:
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in _TRUE_TOKENS:
            return True
        if token in _FALSE_TOKENS:
            return False
    raise ValueError(f"{name} must be true or false")


def _coerce_int(value: Any, name: str) -> int:
    """Accept 45, 45.0, and \"45\" as the same integer; reject anything lossy."""
    if type(value) is bool:
        raise ValueError(f"{name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            number = float(text)
        except ValueError:
            raise ValueError(f"{name} must be an integer") from None
        if number.is_integer():
            return int(number)
    raise ValueError(f"{name} must be an integer")


def normalize_timestamp(value: Any, name: str = "timestamp") -> str:
    text = _require_text(value, name, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO 8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def normalize_date(value: Any, name: str = "date") -> str:
    text = _require_text(value, name, maximum=10)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO date in YYYY-MM-DD format") from error


def _parse_stored_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _evidence_status(attempts: int) -> str:
    if attempts == 0:
        return "unsampled"
    if attempts < 3:
        return "insufficient"
    if attempts < 8:
        return "developing"
    return "established"


def _weighted_domain_plan(question_count: int) -> dict[str, int]:
    raw = {domain_id: question_count * details["weight"] / 100 for domain_id, details in DOMAINS.items()}
    plan = {domain_id: math.floor(value) for domain_id, value in raw.items()}
    remaining = question_count - sum(plan.values())
    ranked = sorted(DOMAINS, key=lambda item: (raw[item] - plan[item], DOMAINS[item]["weight"]), reverse=True)
    for domain_id in ranked[:remaining]:
        plan[domain_id] += 1
    return plan


class StudyMemory:
    """Store learner-owned structured progress without retaining question or chat text."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path or default_database_path()).expanduser()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._telemetry = Telemetry(self.database_path, power_version=POWER_VERSION)
        self._initialize()

    def _emit(self, event: str, session: dict[str, Any]) -> None:
        """Report an adoption event without ever letting it affect the study action.

        Telemetry is a side effect of the session lifecycle, not something the agent can call:
        no MCP tool maps to it, so the model cannot choose to send, skip, or fabricate one.
        """
        try:
            getattr(self._telemetry, event)(session)
        except Exception:
            pass

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS learner_profiles (
                    learner_id TEXT PRIMARY KEY,
                    target_exam_date TEXT,
                    weekly_hours REAL,
                    session_minutes INTEGER,
                    preferences TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS study_sessions (
                    session_id TEXT PRIMARY KEY,
                    learner_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    target_questions INTEGER NOT NULL,
                    domain_plan TEXT NOT NULL,
                    task_plan TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    UNIQUE (learner_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    learner_id TEXT NOT NULL,
                    event_id TEXT,
                    domain TEXT NOT NULL,
                    task_id TEXT,
                    topic_id TEXT,
                    topic TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    activity_type TEXT NOT NULL DEFAULT 'quiz',
                    session_id TEXT,
                    question_id TEXT,
                    response_type TEXT NOT NULL DEFAULT 'single-answer',
                    correct INTEGER NOT NULL CHECK (correct IN (0, 1)),
                    time_spent_seconds INTEGER,
                    confidence TEXT,
                    flagged INTEGER NOT NULL DEFAULT 0,
                    misconception TEXT,
                    rubric_json TEXT,
                    occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS flashcards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    learner_id TEXT NOT NULL,
                    event_id TEXT,
                    task_id TEXT,
                    topic_id TEXT,
                    topic TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    last_reviewed_at TEXT,
                    interval_days INTEGER NOT NULL DEFAULT 0,
                    ease_factor REAL NOT NULL DEFAULT 2.5,
                    repetitions INTEGER NOT NULL DEFAULT 0,
                    review_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS flashcard_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    learner_id TEXT NOT NULL,
                    flashcard_id INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    rating TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL,
                    previous_due_at TEXT NOT NULL,
                    next_due_at TEXT NOT NULL,
                    interval_days INTEGER NOT NULL,
                    ease_factor REAL NOT NULL,
                    repetitions INTEGER NOT NULL,
                    FOREIGN KEY (flashcard_id) REFERENCES flashcards(id),
                    UNIQUE (learner_id, event_id)
                );
                """
            )
            attempt_columns = {
                "event_id": "TEXT",
                "task_id": "TEXT",
                "topic_id": "TEXT",
                "activity_type": "TEXT NOT NULL DEFAULT 'quiz'",
                "session_id": "TEXT",
                "question_id": "TEXT",
                "response_type": "TEXT NOT NULL DEFAULT 'single-answer'",
                "time_spent_seconds": "INTEGER",
                "confidence": "TEXT",
                "flagged": "INTEGER NOT NULL DEFAULT 0",
                "rubric_json": "TEXT",
            }
            for column, definition in attempt_columns.items():
                self._ensure_column(connection, "quiz_attempts", column, definition)
            flashcard_columns = {
                "event_id": "TEXT",
                "task_id": "TEXT",
                "topic_id": "TEXT",
                "last_reviewed_at": "TEXT",
                "interval_days": "INTEGER NOT NULL DEFAULT 0",
                "ease_factor": "REAL NOT NULL DEFAULT 2.5",
                "repetitions": "INTEGER NOT NULL DEFAULT 0",
                "review_count": "INTEGER NOT NULL DEFAULT 0",
            }
            for column, definition in flashcard_columns.items():
                self._ensure_column(connection, "flashcards", column, definition)
            connection.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_attempts_learner_domain
                    ON quiz_attempts (learner_id, domain, occurred_at);
                CREATE INDEX IF NOT EXISTS idx_attempts_learner_task
                    ON quiz_attempts (learner_id, task_id, occurred_at);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_attempts_event
                    ON quiz_attempts (learner_id, event_id) WHERE event_id IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_attempts_session
                    ON quiz_attempts (learner_id, session_id);
                CREATE INDEX IF NOT EXISTS idx_flashcards_due
                    ON flashcards (learner_id, due_at);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_flashcards_event
                    ON flashcards (learner_id, event_id) WHERE event_id IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_reviews_card
                    ON flashcard_reviews (learner_id, flashcard_id, reviewed_at);
                """
            )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            # Additive and outside the learner-memory contract, so SCHEMA_VERSION is unchanged.
            Telemetry.ensure_schema(connection)
            connection.commit()

    @staticmethod
    def _validate_learner(learner_id: Any) -> str:
        return _require_text(learner_id, "learner_id", maximum=128)

    @staticmethod
    def _resolve_taxonomy(
        domain: Any, task_id: Any, topic_id: Any
    ) -> tuple[str, str, str | None, list[str]]:
        """Resolve one canonical (domain, task_id, topic_id) triple from whatever was supplied.

        ``topic_id`` alone determines the task and domain, so a caller that supplies a
        contradictory parent is corrected rather than rejected: losing a graded attempt
        over a redundant field is worse than recording it under its canonical parent.
        """
        corrections: list[str] = []
        domain = _optional_text(domain, "domain", maximum=32)
        task_id = _optional_text(task_id, "task_id", maximum=16)
        topic_id = _optional_text(topic_id, "topic_id", maximum=80)
        if topic_id is not None and topic_id not in TOPICS:
            known = TASKS[task_id]["topic_ids"] if task_id in TASKS else sorted(TOPICS)
            raise ValueError(
                f"unknown topic_id '{topic_id}'. Valid topic_id values"
                + (f" for task_id {task_id}" if task_id in TASKS else "")
                + f": {', '.join(known)}"
            )
        if task_id is not None and task_id not in TASKS:
            raise ValueError(f"unknown task_id '{task_id}'. Valid task_id values: {', '.join(TASKS)}")
        if domain is not None and domain not in DOMAINS:
            raise ValueError(f"unknown domain '{domain}'. Valid domain values: {', '.join(DOMAINS)}")
        if topic_id is None and task_id is None:
            raise ValueError(
                "provide topic_id (preferred) or task_id; call get_exam_catalog for the canonical IDs"
            )
        if topic_id is not None:
            canonical_task = TOPICS[topic_id]["task_id"]
            if task_id is not None and task_id != canonical_task:
                corrections.append(
                    f"task_id {task_id} -> {canonical_task} (canonical parent of topic_id {topic_id})"
                )
            task_id = canonical_task
        canonical_domain = TASKS[task_id]["domain"]
        if domain is not None and domain != canonical_domain:
            corrections.append(
                f"domain {domain} -> {canonical_domain} (canonical parent of task_id {task_id})"
            )
        return canonical_domain, task_id, topic_id, corrections

    def set_profile(
        self,
        learner_id: str,
        target_exam_date: str | None = None,
        weekly_hours: float | None = None,
        session_minutes: int | None = None,
        preferences: str | None = None,
    ) -> dict[str, Any]:
        learner_id = self._validate_learner(learner_id)
        if target_exam_date is not None:
            target_exam_date = normalize_date(target_exam_date, "target_exam_date")
        if weekly_hours is not None:
            if isinstance(weekly_hours, bool) or not isinstance(weekly_hours, (int, float)) or not math.isfinite(weekly_hours):
                raise ValueError("weekly_hours must be a finite number")
            if not 0 < weekly_hours <= 168:
                raise ValueError("weekly_hours must be greater than zero and at most 168")
            weekly_hours = float(weekly_hours)
        if session_minutes is not None:
            if isinstance(session_minutes, bool) or not isinstance(session_minutes, int):
                raise ValueError("session_minutes must be an integer")
            if not 5 <= session_minutes <= 480:
                raise ValueError("session_minutes must be between 5 and 480")
        preferences = _optional_text(preferences, "preferences", maximum=2000)
        now = utc_now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO learner_profiles
                    (learner_id, target_exam_date, weekly_hours, session_minutes, preferences, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(learner_id) DO UPDATE SET
                    target_exam_date = COALESCE(excluded.target_exam_date, learner_profiles.target_exam_date),
                    weekly_hours = COALESCE(excluded.weekly_hours, learner_profiles.weekly_hours),
                    session_minutes = COALESCE(excluded.session_minutes, learner_profiles.session_minutes),
                    preferences = COALESCE(excluded.preferences, learner_profiles.preferences),
                    updated_at = excluded.updated_at
                """,
                (learner_id, target_exam_date, weekly_hours, session_minutes, preferences, now),
            )
            connection.commit()
        return self.get_profile(learner_id)

    def get_profile(self, learner_id: str) -> dict[str, Any]:
        learner_id = self._validate_learner(learner_id)
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT learner_id, target_exam_date, weekly_hours, session_minutes, preferences, updated_at "
                "FROM learner_profiles WHERE learner_id = ?",
                (learner_id,),
            ).fetchone()
        if row is None:
            return {
                "learner_id": learner_id,
                "target_exam_date": None,
                "weekly_hours": None,
                "session_minutes": None,
                "preferences": None,
                "updated_at": None,
                "exists": False,
            }
        return {**dict(row), "exists": True}

    def start_session(
        self,
        learner_id: str,
        session_id: str,
        event_id: str,
        activity_type: str,
        mode: str,
        target_questions: int | None = None,
    ) -> dict[str, Any]:
        learner_id = self._validate_learner(learner_id)
        session_id = _require_text(session_id, "session_id", maximum=128)
        event_id = _require_text(event_id, "event_id", maximum=128)
        raw_activity = _require_text(activity_type, "activity_type", maximum=50).lower().replace("-", "_").strip()
        raw_mode = _require_text(mode, "mode", maximum=50).lower().replace("-", "_").strip()

        if raw_activity not in ACTIVITY_ALIASES:
            raise ValueError(
                f"activity_type '{activity_type}' is not supported. Must be one of: diagnostic, mock, quiz, scenario."
            )
        activity_type = ACTIVITY_ALIASES[raw_activity]

        if activity_type == "diagnostic":
            mode = "diagnostic"
        elif activity_type == "mock":
            if raw_mode in {"mini", "full", "custom"}:
                mode = raw_mode
            elif raw_mode in {"standard", "default"}:
                mode = "mini"
            else:
                mode = "custom"
        elif activity_type in {"quiz", "scenario"}:
            mode = "custom"

        if target_questions is not None and (isinstance(target_questions, bool) or not isinstance(target_questions, int)):
            raise ValueError("target_questions must be an integer")
        if activity_type == "diagnostic":
            target_questions = len(TASKS)
            task_plan = list(TASKS)
            domain_plan = Counter(TASKS[task_id]["domain"] for task_id in task_plan)
        else:
            defaults = {
                ("mock", "mini"): 20,
                ("mock", "full"): 65,
                ("mock", "custom"): 20,
                ("quiz", "custom"): 5,
                ("scenario", "custom"): 1,
            }
            target_questions = target_questions or defaults.get((activity_type, mode), 5)
            if not 1 <= target_questions <= 65:
                raise ValueError("target_questions must be between 1 and 65")
            if activity_type == "scenario":
                domain_plan = {domain_id: 0 for domain_id in DOMAINS}
                task_plan = []
            else:
                domain_plan = _weighted_domain_plan(target_questions)
                task_plan = []
        with closing(self._connect()) as connection:
            existing = connection.execute(
                "SELECT session_id FROM study_sessions WHERE learner_id = ? AND event_id = ?",
                (learner_id, event_id),
            ).fetchone()
            if existing:
                result = self._get_session_with_connection(connection, learner_id, existing["session_id"])
                result["duplicate"] = True
                return result
            conflicting = connection.execute(
                "SELECT learner_id FROM study_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if conflicting:
                raise ValueError("session_id already exists")
            connection.execute(
                """
                INSERT INTO study_sessions
                    (session_id, learner_id, event_id, activity_type, mode, target_questions,
                     domain_plan, task_plan, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    learner_id,
                    event_id,
                    activity_type,
                    mode,
                    target_questions,
                    json.dumps(dict(domain_plan), sort_keys=True),
                    json.dumps(task_plan),
                    utc_now(),
                ),
            )
            connection.commit()
            result = self._get_session_with_connection(connection, learner_id, session_id)
            result["duplicate"] = False
        self._emit("session_started", result)
        return result

    def _get_session_with_connection(
        self, connection: sqlite3.Connection, learner_id: str, session_id: str
    ) -> dict[str, Any]:
        session = connection.execute(
            "SELECT * FROM study_sessions WHERE learner_id = ? AND session_id = ?",
            (learner_id, session_id),
        ).fetchone()
        if session is None:
            raise ValueError("study session not found")
        attempts = connection.execute(
            """
            SELECT domain, task_id, activity_type, correct, time_spent_seconds, flagged
            FROM quiz_attempts WHERE learner_id = ? AND session_id = ? ORDER BY id
            """,
            (learner_id, session_id),
        ).fetchall()
        completed = session["completed_at"] is not None
        objective = [row for row in attempts if row["activity_type"] in OBJECTIVE_ACTIVITIES]
        by_domain: dict[str, dict[str, int]] = {}
        domain_plan = json.loads(session["domain_plan"])
        for domain_id in DOMAINS:
            domain_rows = [row for row in objective if row["domain"] == domain_id]
            by_domain[domain_id] = {
                "attempts": len(domain_rows),
                "correct": sum(row["correct"] for row in domain_rows),
            }
        task_plan = json.loads(session["task_plan"])
        coverage_by_task = {
            task_id: sum(row["task_id"] == task_id for row in objective) for task_id in task_plan
        }
        total_seconds = sum(row["time_spent_seconds"] or 0 for row in attempts)
        return {
            "session_id": session["session_id"],
            "learner_id": learner_id,
            "activity_type": session["activity_type"],
            "mode": session["mode"],
            "target_questions": session["target_questions"],
            "domain_plan": domain_plan,
            "task_plan": task_plan,
            "coverage_by_domain": {
                domain_id: {"planned": domain_plan.get(domain_id, 0), "answered": values["attempts"]}
                for domain_id, values in by_domain.items()
            },
            "coverage_by_task": coverage_by_task,
            "answered": len(attempts),
            "remaining": max(0, session["target_questions"] - len(attempts)),
            "flagged": sum(row["flagged"] for row in attempts),
            "time_spent_seconds": total_seconds,
            "started_at": session["started_at"],
            "completed_at": session["completed_at"],
            "complete": completed,
            "score": (
                {
                    "correct": sum(row["correct"] for row in objective),
                    "attempts": len(objective),
                    "accuracy_percent": round(sum(row["correct"] for row in objective) / len(objective) * 100, 1)
                    if objective
                    else None,
                    "by_domain": by_domain,
                }
                if completed and objective
                else None
            ),
            "disclaimer": "Practice performance is study feedback, not an exam-pass prediction.",
        }

    def get_session(self, learner_id: str, session_id: str) -> dict[str, Any]:
        learner_id = self._validate_learner(learner_id)
        session_id = _require_text(session_id, "session_id", maximum=128)
        with closing(self._connect()) as connection:
            return self._get_session_with_connection(connection, learner_id, session_id)

    def complete_session(self, learner_id: str, session_id: str) -> dict[str, Any]:
        learner_id = self._validate_learner(learner_id)
        session_id = _require_text(session_id, "session_id", maximum=128)
        with closing(self._connect()) as connection:
            session = connection.execute(
                "SELECT completed_at FROM study_sessions WHERE learner_id = ? AND session_id = ?",
                (learner_id, session_id),
            ).fetchone()
            if session is None:
                raise ValueError("study session not found")
            newly_completed = session["completed_at"] is None
            if newly_completed:
                connection.execute(
                    "UPDATE study_sessions SET completed_at = ? WHERE learner_id = ? AND session_id = ?",
                    (utc_now(), learner_id, session_id),
                )
                connection.commit()
            result = self._get_session_with_connection(connection, learner_id, session_id)
        if newly_completed:
            self._emit("session_completed", result)
        return result

    def _session_activity_type(self, learner_id: str, session_id: str) -> str | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT activity_type FROM study_sessions WHERE learner_id = ? AND session_id = ?",
                (learner_id, session_id),
            ).fetchone()
        return row["activity_type"] if row else None

    @staticmethod
    def _normalize_activity(activity_type: Any) -> str:
        raw = _require_text(activity_type, "activity_type", maximum=50).lower().replace("-", "_").strip()
        if raw not in ACTIVITY_ALIASES:
            raise ValueError(f"activity_type must be one of: {', '.join(sorted(ACTIVITY_TYPES))}")
        return ACTIVITY_ALIASES[raw]

    @classmethod
    def _resolve_activity_type(
        cls, activity_type: Any, session_activity: str | None
    ) -> tuple[str, str | None]:
        """Inherit the session's activity when unstated, and defer to it when contradicted."""
        if activity_type is None:
            return session_activity or "quiz", None
        resolved = cls._normalize_activity(activity_type)
        if session_activity is not None and resolved != session_activity:
            return session_activity, (
                f"activity_type {resolved} -> {session_activity} (activity of the named study session)"
            )
        return resolved, None

    @staticmethod
    def _resolve_response_type(response_type: Any, activity_type: str) -> tuple[str, str | None]:
        """Keep response_type consistent with the activity instead of rejecting the attempt."""
        expected_default = "scenario" if activity_type == "scenario" else "single-answer"
        if response_type is None:
            return expected_default, None
        raw = _require_text(response_type, "response_type", maximum=24).lower().strip()
        resolved = RESPONSE_ALIASES.get(raw.replace("-", "_"), raw)
        if resolved not in RESPONSE_TYPES:
            raise ValueError(f"response_type must be one of: {', '.join(sorted(RESPONSE_TYPES))}")
        if (activity_type == "scenario") != (resolved == "scenario"):
            return expected_default, (
                f"response_type {resolved} -> {expected_default} (required by activity_type {activity_type})"
            )
        return resolved, None

    def record_attempt(
        self,
        learner_id: str,
        domain: str | None = None,
        topic: str | None = None,
        difficulty: str = "standard",
        correct: Any = None,
        misconception: str | None = None,
        *,
        event_id: str,
        task_id: str | None = None,
        topic_id: str | None = None,
        activity_type: str | None = None,
        session_id: str | None = None,
        question_id: str | None = None,
        response_type: str | None = None,
        time_spent_seconds: int | None = None,
        confidence: str | None = None,
        flagged: bool = False,
        rubric: dict[str, int] | None = None,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        learner_id = self._validate_learner(learner_id)
        event_id = _require_text(event_id, "event_id", maximum=128)
        domain, task_id, topic_id, corrections = self._resolve_taxonomy(domain, task_id, topic_id)
        topic = _optional_text(topic, "topic", maximum=200) or (
            TOPICS[topic_id]["name"] if topic_id else TASKS[task_id]["name"]
        )
        difficulty = _require_text(difficulty, "difficulty", maximum=20).lower()
        if difficulty not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of: {', '.join(sorted(DIFFICULTIES))}")
        correct = _coerce_bool(correct, "correct")
        flagged = _coerce_bool(flagged, "flagged")
        session_id = _optional_text(session_id, "session_id", maximum=128)
        question_id = _optional_text(question_id, "question_id", maximum=128)
        session_activity = self._session_activity_type(learner_id, session_id) if session_id else None
        activity_type, activity_correction = self._resolve_activity_type(activity_type, session_activity)
        if activity_correction:
            corrections.append(activity_correction)
        response_type, response_correction = self._resolve_response_type(response_type, activity_type)
        if response_correction:
            corrections.append(response_correction)
        if time_spent_seconds is not None:
            time_spent_seconds = _coerce_int(time_spent_seconds, "time_spent_seconds")
            if not 1 <= time_spent_seconds <= 86400:
                raise ValueError("time_spent_seconds must be between 1 and 86400")
        if confidence is not None:
            confidence = _require_text(confidence, "confidence", maximum=10).lower()
            if confidence not in CONFIDENCE_LEVELS:
                raise ValueError(f"confidence must be one of: {', '.join(sorted(CONFIDENCE_LEVELS))}")
        misconception = _optional_text(misconception, "misconception", maximum=500)
        if activity_type == "scenario":
            if not isinstance(rubric, dict) or not rubric:
                raise ValueError(
                    "scenario activity requires a non-empty rubric with integer 0-4 scores for any of: "
                    + ", ".join(sorted(RUBRIC_DIMENSIONS))
                )
            unknown = set(rubric) - RUBRIC_DIMENSIONS
            if unknown:
                raise ValueError(
                    f"unknown rubric dimensions: {', '.join(sorted(unknown))}. "
                    f"Valid dimensions: {', '.join(sorted(RUBRIC_DIMENSIONS))}"
                )
            rubric = {dimension: _coerce_int(score, f"rubric.{dimension}") for dimension, score in rubric.items()}
            if any(not 0 <= score <= 4 for score in rubric.values()):
                raise ValueError("rubric scores must be integers between 0 and 4")
        elif rubric is not None:
            corrections.append("rubric dropped (only scenario activities carry a rubric)")
            rubric = None
        occurred_at = normalize_timestamp(occurred_at, "occurred_at") if occurred_at else utc_now()
        rubric_json = json.dumps(rubric, sort_keys=True) if rubric else None
        with closing(self._connect()) as connection:
            existing = connection.execute(
                "SELECT id FROM quiz_attempts WHERE learner_id = ? AND event_id = ?",
                (learner_id, event_id),
            ).fetchone()
            if existing:
                return {
                    "attempt_id": existing["id"],
                    "recorded": False,
                    "duplicate": True,
                    "note": (
                        f"event_id '{event_id}' was already recorded as attempt {existing['id']}; "
                        "use a new event_id for a new attempt"
                    ),
                }
            if session_id:
                session = connection.execute(
                    "SELECT completed_at FROM study_sessions WHERE learner_id = ? AND session_id = ?",
                    (learner_id, session_id),
                ).fetchone()
                if session is None:
                    raise ValueError(
                        f"study session '{session_id}' not found for learner '{learner_id}'; "
                        "start it with start_study_session or omit session_id"
                    )
                if session["completed_at"] is not None:
                    raise ValueError(
                        f"study session '{session_id}' is already complete; "
                        "start a new session or omit session_id"
                    )
            cursor = connection.execute(
                """
                INSERT INTO quiz_attempts
                    (learner_id, event_id, domain, task_id, topic_id, topic, difficulty,
                     activity_type, session_id, question_id, response_type, correct,
                     time_spent_seconds, confidence, flagged, misconception, rubric_json, occurred_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    learner_id,
                    event_id,
                    domain,
                    task_id,
                    topic_id,
                    topic,
                    difficulty,
                    activity_type,
                    session_id,
                    question_id,
                    response_type,
                    int(correct),
                    time_spent_seconds,
                    confidence,
                    int(flagged),
                    misconception,
                    rubric_json,
                    occurred_at,
                ),
            )
            connection.commit()
        return {
            "attempt_id": cursor.lastrowid,
            "recorded": True,
            "duplicate": False,
            "domain": domain,
            "task_id": task_id,
            "topic_id": topic_id,
            "activity_type": activity_type,
            "session_id": session_id,
            "corrections": corrections,
        }

    @staticmethod
    def _new_stats(identifier: str, name: str) -> dict[str, Any]:
        return {
            "id": identifier,
            "name": name,
            "attempts": 0,
            "correct": 0,
            "recent_attempts": 0,
            "_weighted_correct": 0.0,
            "_evidence": 0.0,
            "_last_attempt": None,
            "_misconceptions": Counter(),
            "overconfident_errors": 0,
            "underconfident_successes": 0,
        }

    @staticmethod
    def _add_objective_attempt(stats: dict[str, Any], row: sqlite3.Row, now: datetime) -> None:
        occurred = _parse_stored_timestamp(row["occurred_at"])
        age_days = max(0.0, (now - occurred).total_seconds() / 86400)
        recency_weight = math.exp(-age_days / 90)
        difficulty_weight = {"foundation": 0.8, "standard": 1.0, "challenging": 1.2}.get(row["difficulty"], 1.0)
        evidence = recency_weight * difficulty_weight
        stats["attempts"] += 1
        stats["correct"] += int(row["correct"])
        stats["recent_attempts"] += int(age_days <= 30)
        stats["_weighted_correct"] += int(row["correct"]) * evidence
        stats["_evidence"] += evidence
        stats["_last_attempt"] = max(stats["_last_attempt"] or occurred, occurred)
        if row["misconception"]:
            stats["_misconceptions"][row["misconception"]] += 1
        stats["overconfident_errors"] += int(row["confidence"] == "high" and not row["correct"])
        stats["underconfident_successes"] += int(row["confidence"] == "low" and row["correct"])

    @staticmethod
    def _finalize_stats(stats: dict[str, Any]) -> dict[str, Any]:
        attempts = stats["attempts"]
        result = {key: value for key, value in stats.items() if not key.startswith("_")}
        result["accuracy_percent"] = round(stats["correct"] / attempts * 100, 1) if attempts else None
        result["mastery_percent"] = (
            round(stats["_weighted_correct"] / stats["_evidence"] * 100, 1) if stats["_evidence"] else None
        )
        result["evidence_status"] = _evidence_status(attempts)
        result["last_attempt_at"] = stats["_last_attempt"].replace(microsecond=0).isoformat() if stats["_last_attempt"] else None
        result["misconceptions"] = [
            {"text": text, "count": count} for text, count in stats["_misconceptions"].most_common(5)
        ]
        return result

    def get_progress(self, learner_id: str) -> dict[str, Any]:
        learner_id = self._validate_learner(learner_id)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT domain, task_id, topic_id, difficulty, activity_type, correct,
                       confidence, misconception, rubric_json, occurred_at
                FROM quiz_attempts WHERE learner_id = ? ORDER BY occurred_at
                """,
                (learner_id,),
            ).fetchall()
        overall = self._new_stats("overall", "Overall objective practice")
        domain_stats: dict[str, dict[str, Any]] = {}
        task_stats: dict[str, dict[str, Any]] = {}
        topic_stats: dict[str, dict[str, Any]] = {}
        for domain_id, details in DOMAINS.items():
            domain_stats[domain_id] = self._new_stats(domain_id, details["name"])
            domain_stats[domain_id]["weight"] = details["weight"]
            domain_stats[domain_id]["scenario_evaluations"] = 0
            domain_stats[domain_id]["_rubric_sums"] = Counter()
            domain_stats[domain_id]["_rubric_counts"] = Counter()
        for task_id, details in TASKS.items():
            task_stats[task_id] = self._new_stats(task_id, details["name"])
            task_stats[task_id]["domain"] = details["domain"]
        for topic_id, details in TOPICS.items():
            topic_stats[topic_id] = self._new_stats(topic_id, details["name"])
            topic_stats[topic_id]["domain"] = details["domain"]
            topic_stats[topic_id]["task_id"] = details["task_id"]
        now = datetime.now(timezone.utc)
        scenario_total = 0
        rubric_sums: Counter[str] = Counter()
        rubric_counts: Counter[str] = Counter()
        for row in rows:
            if row["activity_type"] == "scenario":
                scenario_total += 1
                domain = domain_stats.get(row["domain"])
                if domain:
                    domain["scenario_evaluations"] += 1
                rubric = json.loads(row["rubric_json"]) if row["rubric_json"] else {}
                for dimension, score in rubric.items():
                    rubric_sums[dimension] += score
                    rubric_counts[dimension] += 1
                    if domain:
                        domain["_rubric_sums"][dimension] += score
                        domain["_rubric_counts"][dimension] += 1
                continue
            if row["activity_type"] not in OBJECTIVE_ACTIVITIES:
                continue
            self._add_objective_attempt(overall, row, now)
            if row["domain"] in domain_stats:
                self._add_objective_attempt(domain_stats[row["domain"]], row, now)
            if row["task_id"] in task_stats:
                self._add_objective_attempt(task_stats[row["task_id"]], row, now)
            if row["topic_id"] in topic_stats:
                self._add_objective_attempt(topic_stats[row["topic_id"]], row, now)
        domains = []
        for domain_id, domain in domain_stats.items():
            rubric_average = {
                dimension: round(domain["_rubric_sums"][dimension] / count, 2)
                for dimension, count in domain["_rubric_counts"].items()
            }
            finalized = self._finalize_stats(domain)
            finalized["scenario_rubric_average"] = rubric_average
            finalized["tasks"] = []
            for task_id in DOMAINS[domain_id]["task_ids"]:
                task = self._finalize_stats(task_stats[task_id])
                task["topics"] = [self._finalize_stats(topic_stats[item]) for item in TASKS[task_id]["topic_ids"]]
                finalized["tasks"].append(task)
            domains.append(finalized)
        finalized_overall = self._finalize_stats(overall)
        return {
            "learner_id": learner_id,
            "total_attempts": finalized_overall["attempts"],
            "total_correct": finalized_overall["correct"],
            "overall_accuracy_percent": finalized_overall["accuracy_percent"],
            "overall_mastery_percent": finalized_overall["mastery_percent"],
            "evidence_status": finalized_overall["evidence_status"],
            "misconceptions": finalized_overall["misconceptions"],
            "confidence_calibration": {
                "overconfident_errors": finalized_overall["overconfident_errors"],
                "underconfident_successes": finalized_overall["underconfident_successes"],
            },
            "scenario_evaluations": scenario_total,
            "scenario_rubric_average": {
                dimension: round(rubric_sums[dimension] / count, 2) for dimension, count in rubric_counts.items()
            },
            "domains": domains,
            "disclaimer": "Practice performance is study feedback, not an exam-pass prediction.",
        }

    def save_flashcard(
        self,
        learner_id: str,
        topic: str,
        prompt: str,
        answer: str,
        due_at: str | None = None,
        *,
        event_id: str,
        task_id: str | None = None,
        topic_id: str | None = None,
    ) -> dict[str, Any]:
        learner_id = self._validate_learner(learner_id)
        event_id = _require_text(event_id, "event_id", maximum=128)
        topic = _require_text(topic, "topic", maximum=200)
        prompt = _require_text(prompt, "prompt", maximum=2000)
        answer = _require_text(answer, "answer", maximum=4000)
        if task_id is not None or topic_id is not None:
            _, task_id, topic_id, _ = self._resolve_taxonomy(None, task_id, topic_id)
        due_at = normalize_timestamp(due_at, "due_at") if due_at else utc_now()
        with closing(self._connect()) as connection:
            existing = connection.execute(
                "SELECT id, due_at FROM flashcards WHERE learner_id = ? AND event_id = ?",
                (learner_id, event_id),
            ).fetchone()
            if existing:
                return {"flashcard_id": existing["id"], "saved": False, "duplicate": True, "due_at": existing["due_at"]}
            cursor = connection.execute(
                """
                INSERT INTO flashcards
                    (learner_id, event_id, task_id, topic_id, topic, prompt, answer, due_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (learner_id, event_id, task_id, topic_id, topic, prompt, answer, due_at, utc_now()),
            )
            connection.commit()
        return {"flashcard_id": cursor.lastrowid, "saved": True, "duplicate": False, "due_at": due_at}

    def get_due_flashcards(
        self, learner_id: str, limit: int = 20, as_of: str | None = None
    ) -> list[dict[str, Any]]:
        learner_id = self._validate_learner(learner_id)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")
        as_of = normalize_timestamp(as_of, "as_of") if as_of else utc_now()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, task_id, topic_id, topic, prompt, due_at, interval_days, repetitions, review_count
                FROM flashcards
                WHERE learner_id = ? AND due_at <= ?
                ORDER BY due_at, id LIMIT ?
                """,
                (learner_id, as_of, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_flashcard_answer(self, learner_id: str, flashcard_id: int) -> dict[str, Any]:
        learner_id = self._validate_learner(learner_id)
        if isinstance(flashcard_id, bool) or not isinstance(flashcard_id, int) or flashcard_id < 1:
            raise ValueError("flashcard_id must be a positive integer")
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT id, topic, prompt, answer FROM flashcards WHERE learner_id = ? AND id = ?",
                (learner_id, flashcard_id),
            ).fetchone()
        if row is None:
            raise ValueError("flashcard not found")
        return dict(row)

    @staticmethod
    def _schedule_review(rating: str, interval: int, ease: float, repetitions: int) -> tuple[int, float, int]:
        if rating == "again":
            return 1, max(1.3, ease - 0.2), 0
        if rating == "hard":
            return max(1, round(max(interval, 1) * 1.2)), max(1.3, ease - 0.15), max(1, repetitions)
        if rating == "good":
            next_repetitions = repetitions + 1
            if next_repetitions == 1:
                next_interval = 1
            elif next_repetitions == 2:
                next_interval = 6
            else:
                next_interval = max(1, round(max(interval, 1) * ease))
            return next_interval, ease, next_repetitions
        next_repetitions = repetitions + 1
        next_interval = 4 if next_repetitions == 1 else max(2, round(max(interval, 1) * ease * 1.3))
        return next_interval, min(3.0, ease + 0.15), next_repetitions

    def review_flashcard(
        self,
        learner_id: str,
        flashcard_id: int,
        event_id: str,
        rating: str,
        reviewed_at: str | None = None,
    ) -> dict[str, Any]:
        learner_id = self._validate_learner(learner_id)
        if isinstance(flashcard_id, bool) or not isinstance(flashcard_id, int) or flashcard_id < 1:
            raise ValueError("flashcard_id must be a positive integer")
        event_id = _require_text(event_id, "event_id", maximum=128)
        rating = _require_text(rating, "rating", maximum=10).lower()
        if rating not in FLASHCARD_RATINGS:
            raise ValueError(f"rating must be one of: {', '.join(sorted(FLASHCARD_RATINGS))}")
        reviewed_at = normalize_timestamp(reviewed_at, "reviewed_at") if reviewed_at else utc_now()
        with closing(self._connect()) as connection:
            existing = connection.execute(
                """
                SELECT flashcard_id, rating, reviewed_at, next_due_at, interval_days, ease_factor, repetitions
                FROM flashcard_reviews WHERE learner_id = ? AND event_id = ?
                """,
                (learner_id, event_id),
            ).fetchone()
            if existing:
                return {**dict(existing), "reviewed": False, "duplicate": True}
            card = connection.execute(
                """
                SELECT id, due_at, interval_days, ease_factor, repetitions
                FROM flashcards WHERE learner_id = ? AND id = ?
                """,
                (learner_id, flashcard_id),
            ).fetchone()
            if card is None:
                raise ValueError("flashcard not found")
            interval, ease, repetitions = self._schedule_review(
                rating, card["interval_days"], card["ease_factor"], card["repetitions"]
            )
            next_due = (_parse_stored_timestamp(reviewed_at) + timedelta(days=interval)).replace(microsecond=0).isoformat()
            connection.execute(
                """
                UPDATE flashcards SET due_at = ?, last_reviewed_at = ?, interval_days = ?,
                    ease_factor = ?, repetitions = ?, review_count = review_count + 1
                WHERE learner_id = ? AND id = ?
                """,
                (next_due, reviewed_at, interval, ease, repetitions, learner_id, flashcard_id),
            )
            connection.execute(
                """
                INSERT INTO flashcard_reviews
                    (learner_id, flashcard_id, event_id, rating, reviewed_at, previous_due_at,
                     next_due_at, interval_days, ease_factor, repetitions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    learner_id,
                    flashcard_id,
                    event_id,
                    rating,
                    reviewed_at,
                    card["due_at"],
                    next_due,
                    interval,
                    ease,
                    repetitions,
                ),
            )
            connection.commit()
        return {
            "flashcard_id": flashcard_id,
            "rating": rating,
            "reviewed_at": reviewed_at,
            "next_due_at": next_due,
            "interval_days": interval,
            "ease_factor": round(ease, 2),
            "repetitions": repetitions,
            "reviewed": True,
            "duplicate": False,
        }

    def _due_flashcard_count(self, learner_id: str) -> int:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM flashcards WHERE learner_id = ? AND due_at <= ?",
                (learner_id, utc_now()),
            ).fetchone()
        return int(row["count"])

    def get_recommendation(self, learner_id: str) -> dict[str, Any]:
        learner_id = self._validate_learner(learner_id)
        progress = self.get_progress(learner_id)
        profile = self.get_profile(learner_id)
        due_count = self._due_flashcard_count(learner_id)
        all_tasks = [task for domain in progress["domains"] for task in domain["tasks"]]
        untouched_domains = [domain for domain in progress["domains"] if domain["attempts"] == 0]
        if progress["total_attempts"] == 0:
            selected_domain = max(progress["domains"], key=lambda item: item["weight"])
            selected_task = selected_domain["tasks"][0]
            activity = "diagnostic"
            reason = "No objective baseline exists; sample every official task statement before targeting weaknesses."
        elif untouched_domains:
            selected_domain = max(untouched_domains, key=lambda item: item["weight"])
            selected_task = selected_domain["tasks"][0]
            activity = "targeted-practice"
            reason = "This weighted domain has not been sampled, so evidence is incomplete."
        else:
            under_sampled = [task for task in all_tasks if task["attempts"] < 3]
            if under_sampled:
                selected_task = min(
                    under_sampled,
                    key=lambda item: (item["attempts"], -DOMAINS[item["domain"]]["weight"], item["id"]),
                )
                reason = "This task has fewer than three objective attempts; collect enough evidence before labeling it weak."
            else:
                selected_task = min(
                    all_tasks,
                    key=lambda item: (
                        (item["mastery_percent"] if item["mastery_percent"] is not None else 0)
                        - 20 / math.sqrt(item["attempts"]),
                        -DOMAINS[item["domain"]]["weight"],
                    ),
                )
                reason = "This task has the lowest recency- and difficulty-weighted mastery after accounting for sample size."
            selected_domain = next(item for item in progress["domains"] if item["id"] == selected_task["domain"])
            activity = "targeted-practice"
        selected_topic = min(
            selected_task["topics"],
            key=lambda item: (
                item["attempts"],
                item["mastery_percent"] if item["mastery_percent"] is not None else 0,
                item["id"],
            ),
        )
        session_minutes = profile["session_minutes"] or 30
        review_cards = min(due_count, max(0, session_minutes // 3))
        review_minutes = min(session_minutes // 3, review_cards * 2)
        question_minutes = max(0, session_minutes - review_minutes)
        question_count = max(1, min(20, question_minutes // 3))
        if activity == "diagnostic":
            question_count = len(TASKS)
        session_steps: list[dict[str, Any]] = []
        if review_cards:
            session_steps.append({"activity": "flashcard-review", "cards": review_cards, "minutes": review_minutes})
        session_steps.append(
            {
                "activity": activity,
                "questions": question_count,
                "domain": selected_domain["id"],
                "task_id": selected_task["id"],
                "topic_id": selected_topic["id"],
                "minutes": question_minutes if activity != "diagnostic" else session_minutes,
            }
        )
        schedule: dict[str, Any] = {"session_minutes": session_minutes}
        if profile["weekly_hours"]:
            schedule["recommended_sessions_per_week"] = max(
                1, math.ceil(profile["weekly_hours"] * 60 / session_minutes)
            )
        if profile["target_exam_date"]:
            days = (date.fromisoformat(profile["target_exam_date"]) - date.today()).days
            schedule["days_until_exam"] = days
            if days < 0:
                schedule["urgency"] = "Target date has passed; update the learner profile."
            elif days <= 14:
                schedule["urgency"] = "Exam date is close; prioritize mixed retrieval and timed practice over broad new coverage."
            else:
                schedule["urgency"] = "Continue coverage and spaced retrieval, then increase timed mixed practice closer to the exam."
        return {
            "learner_id": learner_id,
            "recommended_activity": activity,
            "recommended_domain": selected_domain["id"],
            "recommended_domain_name": selected_domain["name"],
            "recommended_task_id": selected_task["id"],
            "recommended_task_name": selected_task["name"],
            "recommended_topic_id": selected_topic["id"],
            "recommended_topic_name": selected_topic["name"],
            "evidence_status": selected_task["evidence_status"],
            "reason": reason,
            "due_flashcards": due_count,
            "session_steps": session_steps,
            "schedule": schedule,
            "disclaimer": "This is study feedback, not an exam-pass prediction.",
        }
