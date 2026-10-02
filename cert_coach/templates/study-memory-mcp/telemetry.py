"""Adoption telemetry for the AWS SAA-C03 Study Coach.

Reports *that* a colleague ran a study session, never how they did. The question this answers
is whether the Power is being used; activity metadata answers it on its own, so no
correctness, mastery, domain, task, topic, difficulty, confidence, misconception, rubric, or
flashcard value is ever placed on the wire. ``PAYLOAD_FIELDS`` is an allowlist enforced on the
way out, so a later caller cannot widen the payload by passing extra keys.

``learner_id`` is excluded deliberately. It adds nothing to an adoption count while linking
this monitor to the learner's study records.

Three properties this module has to hold:

* **The agent cannot trigger it.** Emission happens inside the store's session lifecycle, and
  no MCP tool is exposed for it, so the model has no verb to send, skip, or fabricate a
  report. ``tests/test_telemetry.py`` pins this.
* **It cannot break studying.** Every failure path is silent and off the calling thread. A
  study session must never fail, stall, or slow down because a monitoring endpoint is
  unreachable.
* **Offline still counts.** Events queue in a local outbox and flush in the background, so a
  colleague studying on a plane shows up as active once the laptop reconnects rather than
  looking idle.
"""

from __future__ import annotations

import json
import os
import platform
import socket
import sqlite3
import threading
import urllib.error
import urllib.request
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from telemetry_config import TELEMETRY_ENDPOINT, TELEMETRY_TOKEN
except ImportError:  # a checkout without the committed config stays inert rather than failing
    TELEMETRY_ENDPOINT = ""
    TELEMETRY_TOKEN = ""

BATCH_SIZE = 50
MAX_ATTEMPTS = 10
MAX_AGE_DAYS = 30
DEFAULT_TIMEOUT_SECONDS = 3.0
MAX_TIMEOUT_SECONDS = 30.0
USER_AGENT = "aws-saa-study-coach-telemetry/1"
LOOPBACK_PREFIXES = ("http://127.0.0.1", "http://localhost", "http://[::1]")

EVENT_TYPES = {"session_started", "session_completed"}

#: Every key a payload may carry. Anything absent from this tuple cannot leave the machine.
PAYLOAD_FIELDS = (
    "event_id",
    "event_type",
    "install_id",
    "user_key",
    "power_version",
    "activity_type",
    "mode",
    "target_questions",
    "questions_answered",
    "duration_seconds",
    "client_platform",
    "occurred_at",
)

_TRUE_TOKENS = {"1", "true", "t", "yes", "y", "on"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _default_user_key() -> str:
    """Identify the colleague behind an install without reaching for anything sensitive."""
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    try:
        host = socket.gethostname() or "unknown"
    except OSError:
        host = "unknown"
    return f"{user}@{host}"[:128]


def _resolve_timeout() -> float:
    raw = os.environ.get("AWS_SAA_TELEMETRY_TIMEOUT")
    if not raw:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    if not 0 < timeout <= MAX_TIMEOUT_SECONDS:
        return DEFAULT_TIMEOUT_SECONDS
    return timeout


class Telemetry:
    """Queue and forward adoption events, or do nothing at all when unconfigured."""

    def __init__(self, database_path: str | Path, *, power_version: str) -> None:
        self.database_path = Path(database_path)
        self.power_version = power_version
        # The committed endpoint is the normal path; the override exists so the tests can point
        # at a local stub without a deployed API.
        self.endpoint = (os.environ.get("AWS_SAA_TELEMETRY_URL") or TELEMETRY_ENDPOINT).strip()
        self.token = (os.environ.get("AWS_SAA_TELEMETRY_TOKEN") or TELEMETRY_TOKEN).strip()
        self.user_key = (os.environ.get("AWS_SAA_TELEMETRY_USER") or "").strip() or _default_user_key()
        self.timeout = _resolve_timeout()
        self.disabled = (os.environ.get("AWS_SAA_TELEMETRY_DISABLED") or "").strip().lower() in _TRUE_TOKENS
        self._lock = threading.Lock()
        self._flushing = False
        self._pending = False
        self._install_id: str | None = None

    @property
    def enabled(self) -> bool:
        """Only an https endpoint with no kill switch set turns telemetry on.

        Loopback over plain http is the one exception, so the test suite can run a stub
        endpoint without a certificate. Such a request never leaves the machine.
        """
        if self.disabled or not self.endpoint:
            return False
        return self.endpoint.startswith("https://") or self.endpoint.startswith(LOOPBACK_PREFIXES)

    @staticmethod
    def ensure_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS telemetry_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS telemetry_outbox (
                event_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_attempt_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_telemetry_outbox_created
                ON telemetry_outbox (created_at);
            """
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _resolve_install_id(self, connection: sqlite3.Connection) -> str:
        """A stable per-database ID, so reinstalling Kiro does not read as a new colleague."""
        if self._install_id is not None:
            return self._install_id
        row = connection.execute("SELECT value FROM telemetry_state WHERE key = 'install_id'").fetchone()
        if row is None:
            connection.execute(
                "INSERT OR IGNORE INTO telemetry_state (key, value) VALUES ('install_id', ?)",
                (str(uuid.uuid4()),),
            )
            row = connection.execute("SELECT value FROM telemetry_state WHERE key = 'install_id'").fetchone()
        self._install_id = row["value"]
        return self._install_id

    def record(self, event_type: str, event_key: str, **fields: Any) -> None:
        """Enqueue one adoption event and kick off a background flush.

        Never raises: a monitoring problem must not surface as a study failure.
        """
        if not self.enabled:
            return
        try:
            self._enqueue(event_type, event_key, fields)
        except Exception:
            return
        self._start_flush()

    def _enqueue(self, event_type: str, event_key: str, fields: dict[str, Any]) -> None:
        if event_type not in EVENT_TYPES:
            return
        event_id = f"{event_type}:{event_key}"[:128]
        with closing(self._connect()) as connection:
            self.ensure_schema(connection)
            candidate = {
                "event_id": event_id,
                "event_type": event_type,
                "install_id": self._resolve_install_id(connection),
                "user_key": self.user_key,
                "power_version": self.power_version,
                "client_platform": platform.system() or "unknown",
                "occurred_at": _utc_now(),
                **fields,
            }
            # Filter last and by allowlist, so a caller cannot widen the payload.
            payload = {key: candidate[key] for key in PAYLOAD_FIELDS if candidate.get(key) is not None}
            connection.execute(
                "INSERT OR IGNORE INTO telemetry_outbox (event_id, payload, created_at) VALUES (?, ?, ?)",
                (event_id, json.dumps(payload, sort_keys=True), _utc_now()),
            )
            connection.commit()

    def _start_flush(self) -> None:
        with self._lock:
            if self._flushing:
                # A flush is already running. Flag the new event rather than dropping it, or
                # it would sit in the outbox until the next session and session_completed
                # would arrive a session late.
                self._pending = True
                return
            self._flushing = True
            self._pending = False
        threading.Thread(target=self._flush_quietly, name="saa-telemetry", daemon=True).start()

    def _flush_quietly(self) -> None:
        try:
            while True:
                # flush() returns 0 on an empty outbox *and* on a failed delivery, so this
                # drains a backlog in batches without spinning against a dead endpoint.
                while self.flush():
                    pass
                with self._lock:
                    if not self._pending:
                        return
                    self._pending = False
        except Exception:
            pass
        finally:
            with self._lock:
                self._flushing = False

    def flush(self) -> int:
        """Drain the outbox. Returns the number of events the endpoint accepted."""
        if not self.enabled:
            return 0
        delivered = 0
        with closing(self._connect()) as connection:
            self.ensure_schema(connection)
            self._discard_exhausted(connection)
            rows = connection.execute(
                "SELECT event_id, payload FROM telemetry_outbox ORDER BY created_at, event_id LIMIT ?",
                (BATCH_SIZE,),
            ).fetchall()
            if not rows:
                connection.commit()
                return 0
            batch = []
            for row in rows:
                try:
                    batch.append(json.loads(row["payload"]))
                except json.JSONDecodeError:
                    connection.execute("DELETE FROM telemetry_outbox WHERE event_id = ?", (row["event_id"],))
            connection.commit()
            if not batch:
                return 0
            if self._post(batch):
                connection.executemany(
                    "DELETE FROM telemetry_outbox WHERE event_id = ?",
                    [(item["event_id"],) for item in batch],
                )
                delivered = len(batch)
            else:
                connection.executemany(
                    "UPDATE telemetry_outbox SET attempts = attempts + 1, last_attempt_at = ? WHERE event_id = ?",
                    [(_utc_now(), item["event_id"]) for item in batch],
                )
            connection.commit()
        return delivered

    def _discard_exhausted(self, connection: sqlite3.Connection) -> None:
        """Bound the outbox so a permanently dead endpoint cannot grow the learner's database."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)).replace(microsecond=0).isoformat()
        connection.execute(
            "DELETE FROM telemetry_outbox WHERE attempts >= ? OR created_at < ?",
            (MAX_ATTEMPTS, cutoff),
        )

    def _post(self, batch: list[dict[str, Any]]) -> bool:
        body = json.dumps({"events": batch}, sort_keys=True).encode("utf-8")
        headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(self.endpoint, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return 200 <= response.status < 300
        except urllib.error.HTTPError as error:
            # A 4xx other than 408/429 will not succeed on retry. Treat it as delivered so one
            # rejected event cannot wedge the queue behind it forever.
            return 400 <= error.code < 500 and error.code not in (408, 429)
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def session_started(self, session: dict[str, Any]) -> None:
        self.record(
            "session_started",
            str(session.get("session_id")),
            activity_type=session.get("activity_type"),
            mode=session.get("mode"),
            target_questions=session.get("target_questions"),
        )

    def session_completed(self, session: dict[str, Any]) -> None:
        duration = None
        started_at, completed_at = session.get("started_at"), session.get("completed_at")
        if started_at and completed_at:
            try:
                duration = int((_parse_timestamp(completed_at) - _parse_timestamp(started_at)).total_seconds())
            except ValueError:
                duration = None
        self.record(
            "session_completed",
            str(session.get("session_id")),
            activity_type=session.get("activity_type"),
            mode=session.get("mode"),
            target_questions=session.get("target_questions"),
            questions_answered=session.get("answered"),
            duration_seconds=duration,
        )
