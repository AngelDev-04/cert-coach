# Adoption telemetry design

> **Status: removed from the codebase.** The study-memory MCP server makes no network calls.
> This document is the single source of truth for rebuilding the feature: it keeps the design
> rationale, the exact integration points, the ingest API contract, the deployment steps, and
> (in the appendices) the complete client source and test suite as they last shipped.

## 1. Purpose and boundary

A team running the coach may want to know whether colleagues are using it. That question is
answerable from activity metadata alone, so the design reports **that** a session happened and
never **how it went**. The distinction is the whole design: widening the payload would turn a
usage monitor into performance surveillance, which is a different thing with different consent
requirements.

`learner_id` is excluded for the same reason. It adds nothing to an adoption count while linking
the monitor to the learner's study records.

## 2. Four constraints that shaped every decision

Each one is load-bearing and each was pinned by a test (Appendix C).

1. **The AI agent must never trigger the upload.** Emission is a side effect of the deterministic
   session actions in `store.py`. No MCP tool exists for telemetry and `MEMORY_HANDLERS` gains no
   entry, so the model has no verb with which to send, skip, or fabricate a report. Pinned by
   `test_no_mcp_tool_can_send_telemetry` (exactly 13 tools, none matching telemetry/sync/upload).
2. **Zero configuration for learners.** No env var, no `mcp.json` edit, no config file to drop
   in. The endpoint ships as committed constants in `study-memory-mcp/telemetry_config.py`.
3. **No study performance data on the wire, ever.** Enforced three times: an allowlist in the
   client, a schema validator rejecting unknown keys server-side, and a database table that has
   no column to hold it.
4. **Telemetry must never break studying.** Every failure path is silent and off the calling
   thread. An unreachable endpoint cannot make a study action fail, block, or slow down.

## 3. Payload

`PAYLOAD_FIELDS` in `telemetry.py` is an allowlist applied **last**, after the caller's fields are
merged. A caller passing `correct` or `topic_id` therefore cannot widen what leaves the machine.

| Field | Source |
| --- | --- |
| `event_id` | `"{event_type}:{session_id}"` — the ingest primary key / idempotency key |
| `event_type` | `session_started` or `session_completed` |
| `install_id` | random UUID in `telemetry_state`, stable for the life of the database |
| `user_key` | `username@hostname`, or `AWS_SAA_TELEMETRY_USER` |
| `power_version` | `store.POWER_VERSION` |
| `activity_type`, `mode` | the session's own plan |
| `target_questions`, `questions_answered` | counts |
| `duration_seconds` | `completed_at - started_at` |
| `client_platform` | `platform.system()` |
| `occurred_at` | UTC ISO 8601 |

**Never sent:** correctness, accuracy, mastery, domain/task/topic IDs, difficulty, confidence,
misconceptions, scenario rubrics, flashcard prompts and answers, question text, chat, `learner_id`.

`session_started` is the load-bearing event: a learner who abandons a session never reaches
`complete_session`, so adoption must not depend on completion. `session_completed` fires only on
the `NULL` → timestamp transition, so completing an already-complete session reports once.

## 4. Configuration

`study-memory-mcp/telemetry_config.py` carries the deployed endpoint and bearer token as
committed constants (Appendix B). The team fills them in once and re-shares the build; learners
configure nothing. While `TELEMETRY_ENDPOINT` is empty the client is inert and transmits nothing.

It cannot live in `mcp.json`: Kiro never expands `${PLUGIN_ROOT}` and expands real environment
variables only after the user approves them via `kiroAgent.mcpApprovedEnvVars`, which is manual
setup and violates constraint 2. A committed Python constant sidesteps both.

Environment variables exist only as escape hatches, never as required setup:

| Variable | Effect |
| --- | --- |
| `AWS_SAA_TELEMETRY_DISABLED=1` | Kill switch for one machine |
| `AWS_SAA_TELEMETRY_URL` | Override the endpoint (the test suite points this at a local stub) |
| `AWS_SAA_TELEMETRY_TOKEN` | Override the bearer token |
| `AWS_SAA_TELEMETRY_USER` | Override the reported identity |
| `AWS_SAA_TELEMETRY_TIMEOUT` | Request timeout, default 3s, capped at 30s |

Only `https://` endpoints are accepted, with one exception: loopback over plain `http://`, so the
test suite can run a stub without a certificate.

**The committed token is a spam gate, not a security boundary.** Anyone who can read the
repository can read it. That is tolerable only because the endpoint is write-only, the payload
carries no study performance data, and the API stage is throttled. **Never commit a real token
to a public repository** — for a public build, keep the constants empty.

## 5. Delivery

Events are queued in `telemetry_outbox` in the learner's own SQLite database and flushed on a
background daemon thread, so studying offline still counts (the backlog flushes when the laptop
reconnects) and an unreachable endpoint can never make a study action fail, block, or slow down.

- Up to 50 events per request. A 2xx deletes the batch.
- A connection error increments `attempts` and leaves the rows for a later flush.
- A 4xx other than 408/429 also deletes them: it will not succeed on retry, and one rejected
  event must not wedge the queue behind it.
- `_start_flush` / `_flush_quietly` use a `_flushing` + `_pending` pair. Without `_pending`, an
  event queued while a flush was in flight was dropped until the next session. A test covers it.
- `_discard_exhausted` runs at the *start* of `flush()`: rows are discarded once `attempts`
  reaches 10 or they pass 30 days, on the following flush. A dead endpoint cannot grow the DB.
- Calling `flush()` manually while the background thread runs can POST a batch twice (the
  read-then-delete is not transactional). The idempotent server-side upsert absorbs it.

## 6. Storage

`telemetry_state` (key/value, holds `install_id`) and `telemetry_outbox` (`event_id` PK,
`payload`, `created_at`, `attempts`, `last_attempt_at`) live in the study-memory database and are
created by `Telemetry.ensure_schema` during `StudyMemory._initialize`. They are additive and
outside the learner-memory contract, so `SCHEMA_VERSION` stays at `2`; bumping it would wrongly
imply the study schema changed. Databases created while telemetry was active may still contain
these two tables; they are harmless and unused.

## 7. How to re-enable (step by step)

1. **Restore the client.** Create `cert_coach/templates/study-memory-mcp/telemetry.py` from
   Appendix A and `telemetry_config.py` from Appendix B (stdlib only; no new dependencies).
2. **Wire it into `cert_coach/templates/study-memory-mcp/store.py`** — four touch points:

   ```python
   # (a) imports, next to `from catalog import ...`
   from telemetry import Telemetry

   # (b) StudyMemory.__init__, right before self._initialize()
   self._telemetry = Telemetry(self.database_path, power_version=POWER_VERSION)

   # (c) new method on StudyMemory
   def _emit(self, event: str, session: dict[str, Any]) -> None:
       """Report an adoption event without ever letting it affect the study action.

       Telemetry is a side effect of the session lifecycle, not something the agent can call:
       no MCP tool maps to it, so the model cannot choose to send, skip, or fabricate one.
       """
       try:
           getattr(self._telemetry, event)(session)
       except Exception:
           pass

   # (d) StudyMemory._initialize, after `PRAGMA user_version = ...`, before commit()
   # Additive and outside the learner-memory contract, so SCHEMA_VERSION is unchanged.
   Telemetry.ensure_schema(connection)
   ```

   Then emit from the session lifecycle, **after** the commit and outside the `with` block:

   ```python
   # start_session: on the NON-duplicate path only, after result["duplicate"] = False
   self._emit("session_started", result)

   # complete_session: only on the NULL -> timestamp transition
   if newly_completed:
       self._emit("session_completed", result)
   ```
3. **Restore the tests** as `tests/test_telemetry.py` from Appendix C and run
   `uv run python3 -m unittest discover -s tests`.
4. **Fix the known issue** before shipping: the loopback check uses `startswith` on
   `LOOPBACK_PREFIXES`, so `http://localhost.example.com` would pass as "loopback" and send the
   token in clear text. Parse the URL and compare the hostname exactly instead.
5. **Deploy the ingest API** (section 8) and fill in the two constants.
6. **Restore the user-facing disclosure**: a "What is transmitted" section in
   `study-memory-mcp/README.md` and an "Adoption reporting" note in `POWER.md` listing exactly
   what is and is not sent and how to use the kill switch.
7. **Tell the team before shipping.** The monitor identifies individuals (`username@hostname`)
   and is on by default once the endpoint is filled in. Announce it together with the kill switch.

## 8. Ingest API (server side)

A separate Chalice (AWS Lambda) service behind API Gateway, writing to MySQL on RDS.

**Routes** — prefix `/v1/study-telemetry`:

- `POST /events` — `Authorization: Bearer <INGEST_TOKEN>` (compared with `hmac.compare_digest`
  on bytes). Body `{"events": [ ... ]}`, up to 50 events. `201 {"message": "Accepted", "data":
  {"accepted": N}, "errors": {}}`; `401` bad token; `422` invalid payload (unknown keys are
  rejected); `503` when `INGEST_TOKEN` is unset. Write-only: nothing is read back through the API.
- `GET /health` — liveness.

**Schema** — one table, `study_activity`, primary key `event_id VARCHAR(128)` so replays upsert
instead of inflating counts; InnoDB / utf8mb4; `received_at` defaults to `CURRENT_TIMESTAMP`. It
has **no column for study performance data** — the schema is the last line of the privacy
contract. The upsert uses MySQL 8.0.19+ row-alias syntax (`... AS new ON DUPLICATE KEY UPDATE`).
Two reporting views:

- `v_user_activity` — per `user_key`: first/last seen, sessions started/completed, total study
  minutes, days since last session.
- `v_weekly_adoption` — per ISO week: distinct users, distinct installs, sessions completed.

**Contract test** — the ingest repo should import this client's `telemetry.py` and assert the
wire format matches its validation schema. It is the only guard against the two sides drifting:
change `PAYLOAD_FIELDS`, `EVENT_TYPES`, or `BATCH_SIZE` on both sides together.

**Deploy:**

1. RDS MySQL 8.0.19+, `db.t4g.micro`, Single-AZ, 20 GB gp3, **public access off**.
2. Security group on RDS allows 3306 only from the Lambda's security group.
3. Apply the `study_activity` migration.
4. Deploy with Chalice, Lambda attached to private subnets.
5. Lambda env vars: `MYSQL_URI`, `INGEST_TOKEN`. Leave CORS off — the client is a Python process
   that sends no `Origin` and never preflights.
6. If credentials come from Secrets Manager, add an interface VPC endpoint (no NAT needed).
7. **Enable API Gateway stage throttling** (the token is a spam gate, not a boundary).

**End-to-end verification:**

1. `tools/list` on the MCP server shows 13 tools, none telemetry.
2. Point `AWS_SAA_TELEMETRY_URL` at a local stub, run a diagnostic, confirm both events arrive and
   the outbox drains.
3. `curl -X POST -H "Authorization: Bearer …" -d @sample.json <url>` → 201; re-POST the same
   payload and confirm the row count does not change.
4. `SELECT * FROM v_user_activity ORDER BY last_seen DESC;`
5. Block the endpoint, run a session, confirm it completes normally and flushes later.
6. `AWS_SAA_TELEMETRY_DISABLED=1` → nothing queued or sent.

## Appendix A — `study-memory-mcp/telemetry.py`

````python
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
````

## Appendix B — `study-memory-mcp/telemetry_config.py`

````python
"""Deployed adoption-telemetry endpoint, shipped with the Power.

DevOps fills these two constants in once, after deploying the ingest API, and re-shares the
Power. Colleagues then configure nothing: no environment variable, no ``mcp.json`` edit, no
config file to drop in. That is the whole point of committing them here.

They cannot live in ``mcp.json``. ``scripts/validate_project.py`` rejects any ``${`` in that
file's args or env values, because Kiro never expands ``${PLUGIN_ROOT}`` and expands real
environment variables only after the user approves them via ``kiroAgent.mcpApprovedEnvVars``.
A committed Python constant sidesteps both problems.

While ``TELEMETRY_ENDPOINT`` is empty the Power ships inert and transmits nothing, so an
un-deployed checkout behaves exactly as it did before telemetry existed.

The token is a spam gate, not a security boundary: anyone who can read this repository can
read it. That is acceptable only because the endpoint is write-only and the payload carries
no study performance data (see ``docs/telemetry-design.md``). Never commit a real token to a
public repository, and throttle the API Gateway stage.
"""

from __future__ import annotations

#: Full URL of the ingest route, e.g.
#: "https://<api-id>.execute-api.<region>.amazonaws.com/<stage>/v1/study-telemetry/events"
TELEMETRY_ENDPOINT = ""

#: Shared bearer token checked by the ingest Lambda (same value as its INGEST_TOKEN).
TELEMETRY_TOKEN = ""
````

## Appendix C — `tests/test_telemetry.py`

````python
from __future__ import annotations

import json
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "cert_coach" / "templates" / "study-memory-mcp"))

import server as mcp_server  # noqa: E402
from store import StudyMemory  # noqa: E402
from telemetry import MAX_ATTEMPTS, PAYLOAD_FIELDS, Telemetry  # noqa: E402

TELEMETRY_ENV = {
    "AWS_SAA_TELEMETRY_URL": "",
    "AWS_SAA_TELEMETRY_TOKEN": "",
    "AWS_SAA_TELEMETRY_USER": "",
    "AWS_SAA_TELEMETRY_TIMEOUT": "",
    "AWS_SAA_TELEMETRY_DISABLED": "",
}

# Study evidence that must never appear in an adoption payload. Sending any of these would
# turn a usage monitor into performance surveillance of colleagues.
FORBIDDEN_FIELDS = (
    "learner_id",
    "correct",
    "domain",
    "task_id",
    "topic_id",
    "topic",
    "difficulty",
    "confidence",
    "misconception",
    "rubric",
    "accuracy_percent",
    "score",
    "prompt",
    "answer",
)


class _StubHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.server.requests.append(
            {"body": json.loads(body), "authorization": self.headers.get("Authorization")}
        )
        self.send_response(self.server.status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"accepted": 0}')

    def log_message(self, *args: object) -> None:
        """Keep the stub silent so test output stays readable."""


@contextmanager
def stub_endpoint(status_code: int = 201):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    server.requests = []
    server.status_code = status_code
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}/events"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def unreachable_url() -> str:
    """A port nothing is listening on, so delivery fails without waiting on a network timeout."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return f"http://127.0.0.1:{port}/events"


@contextmanager
def telemetry_env(**overrides: str):
    with mock.patch.dict("os.environ", {**TELEMETRY_ENV, **overrides}, clear=False), \
         mock.patch("telemetry.TELEMETRY_ENDPOINT", overrides.get("AWS_SAA_TELEMETRY_URL", "")), \
         mock.patch("telemetry.TELEMETRY_TOKEN", overrides.get("AWS_SAA_TELEMETRY_TOKEN", "")):
        yield


class TelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "learner.sqlite3"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def outbox(self) -> list[sqlite3.Row]:
        with sqlite3.connect(self.database) as connection:
            connection.row_factory = sqlite3.Row
            try:
                return connection.execute(
                    "SELECT * FROM telemetry_outbox ORDER BY event_id"
                ).fetchall()
            except sqlite3.OperationalError:
                return []

    def payloads(self) -> list[dict]:
        return [json.loads(row["payload"]) for row in self.outbox()]

    def run_session(self, memory: StudyMemory, session_id: str = "s-1", complete: bool = True) -> None:
        memory.start_session("learner-01", session_id, f"{session_id}-start", "quiz", "custom", 5)
        if complete:
            memory.complete_session("learner-01", session_id)

    # ------------------------------------------------------------------ off by default

    def test_unconfigured_power_transmits_nothing(self) -> None:
        with telemetry_env():
            memory = StudyMemory(self.database)
            self.assertFalse(memory._telemetry.enabled)
            self.run_session(memory)
        self.assertEqual(self.outbox(), [])

    def test_kill_switch_disables_a_configured_endpoint(self) -> None:
        with telemetry_env(AWS_SAA_TELEMETRY_URL="https://example.invalid/events",
                           AWS_SAA_TELEMETRY_DISABLED="1"):
            memory = StudyMemory(self.database)
            self.assertFalse(memory._telemetry.enabled)
            self.run_session(memory)
        self.assertEqual(self.outbox(), [])

    def test_plain_http_endpoint_off_loopback_is_treated_as_unset(self) -> None:
        with telemetry_env(AWS_SAA_TELEMETRY_URL="http://telemetry.internal/events"):
            self.assertFalse(Telemetry(self.database, power_version="0.3.0").enabled)

    # ------------------------------------------------------- the agent cannot trigger it

    def test_no_mcp_tool_can_send_telemetry(self) -> None:
        # Telemetry is a side effect of the session lifecycle. If a tool ever exposes it, the
        # model gains a verb to send, skip, or fabricate a report, which this pins against.
        names = {tool["name"] for tool in mcp_server.TOOLS}
        self.assertEqual(len(names), 13)
        for name in names | set(mcp_server.MEMORY_HANDLERS):
            for verb in ("telemetry", "sync", "upload", "report_usage"):
                self.assertNotIn(verb, name)
        self.assertNotIn("telemetry", json.dumps(mcp_server.TOOLS).lower())

    # ------------------------------------------------------------------ payload contract

    def test_payload_carries_only_allowlisted_adoption_fields(self) -> None:
        with telemetry_env(AWS_SAA_TELEMETRY_URL=unreachable_url()):
            telemetry = Telemetry(self.database, power_version="0.3.0")
            with mock.patch.object(Telemetry, "_start_flush", lambda self: None):
                telemetry.record(
                    "session_started",
                    "s-1",
                    activity_type="quiz",
                    mode="custom",
                    # Everything below is study evidence a caller might wrongly pass in.
                    learner_id="learner-01",
                    correct=True,
                    topic_id="iam-policy-evaluation",
                    misconception="confused gateway and interface endpoints",
                )
        payload = self.payloads()[0]
        self.assertLessEqual(set(payload), set(PAYLOAD_FIELDS))
        for field in FORBIDDEN_FIELDS:
            self.assertNotIn(field, payload)
        self.assertEqual(payload["event_type"], "session_started")
        self.assertEqual(payload["activity_type"], "quiz")
        self.assertEqual(payload["power_version"], "0.3.0")

    def test_session_events_never_leak_study_evidence(self) -> None:
        with telemetry_env(AWS_SAA_TELEMETRY_URL=unreachable_url()):
            with mock.patch.object(Telemetry, "_start_flush", lambda self: None):
                memory = StudyMemory(self.database)
                memory.start_session("learner-01", "s-1", "s-1-start", "mock", "mini")
                memory.record_attempt(
                    learner_id="learner-01",
                    event_id="a-1",
                    topic_id="iam-policy-evaluation",
                    correct=True,
                    session_id="s-1",
                    misconception="mixed up SCP and IAM policy evaluation",
                )
                memory.complete_session("learner-01", "s-1")
        payloads = self.payloads()
        self.assertEqual({item["event_type"] for item in payloads},
                         {"session_started", "session_completed"})
        serialized = json.dumps(payloads)
        self.assertNotIn("iam-policy-evaluation", serialized)
        self.assertNotIn("mixed up SCP", serialized)
        self.assertNotIn("learner-01", serialized)
        completed = next(item for item in payloads if item["event_type"] == "session_completed")
        self.assertEqual(completed["questions_answered"], 1)
        self.assertEqual(completed["activity_type"], "mock")
        self.assertIsNotNone(completed["duration_seconds"])

    def test_named_identity_is_reported_and_overridable(self) -> None:
        with telemetry_env(AWS_SAA_TELEMETRY_URL=unreachable_url(),
                           AWS_SAA_TELEMETRY_USER="ana@LAPTOP-07"):
            telemetry = Telemetry(self.database, power_version="0.3.0")
            with mock.patch.object(Telemetry, "_start_flush", lambda self: None):
                telemetry.record("session_started", "s-1", activity_type="quiz", mode="custom")
        self.assertEqual(self.payloads()[0]["user_key"], "ana@LAPTOP-07")

    # ---------------------------------------------------------------------- reliability

    def test_unreachable_endpoint_never_breaks_a_study_session(self) -> None:
        with telemetry_env(AWS_SAA_TELEMETRY_URL=unreachable_url()):
            memory = StudyMemory(self.database)
            session = memory.start_session("learner-01", "s-1", "s-1-start", "quiz", "custom", 5)
            completed = memory.complete_session("learner-01", "s-1")
            self.assertEqual(session["session_id"], "s-1")
            self.assertTrue(completed["complete"])
            self.assertEqual(memory._telemetry.flush(), 0)
        rows = self.outbox()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["attempts"] >= 1 for row in rows))

    def test_offline_events_flush_once_the_endpoint_returns(self) -> None:
        with stub_endpoint() as (stub, url):
            with telemetry_env(AWS_SAA_TELEMETRY_URL=url, AWS_SAA_TELEMETRY_TOKEN="s3cret"):
                with mock.patch.object(Telemetry, "_start_flush", lambda self: None):
                    memory = StudyMemory(self.database)
                    self.run_session(memory)
                self.assertEqual(len(self.outbox()), 2)
                self.assertEqual(memory._telemetry.flush(), 2)
        self.assertEqual(self.outbox(), [])
        self.assertEqual(len(stub.requests), 1)
        request = stub.requests[0]
        self.assertEqual(request["authorization"], "Bearer s3cret")
        self.assertEqual(len(request["body"]["events"]), 2)

    def test_background_flush_delivers_without_an_explicit_call(self) -> None:
        with stub_endpoint() as (stub, url):
            with telemetry_env(AWS_SAA_TELEMETRY_URL=url):
                memory = StudyMemory(self.database)
                self.run_session(memory)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not self.outbox() == []:
                    time.sleep(0.05)
        self.assertEqual(self.outbox(), [])
        self.assertTrue(stub.requests)

    def test_completing_twice_reports_one_event(self) -> None:
        with telemetry_env(AWS_SAA_TELEMETRY_URL=unreachable_url()):
            with mock.patch.object(Telemetry, "_start_flush", lambda self: None):
                memory = StudyMemory(self.database)
                memory.start_session("learner-01", "s-1", "s-1-start", "quiz", "custom", 5)
                memory.complete_session("learner-01", "s-1")
                memory.complete_session("learner-01", "s-1")
        completed = [item for item in self.payloads() if item["event_type"] == "session_completed"]
        self.assertEqual(len(completed), 1)

    def test_duplicate_start_event_id_reports_one_event(self) -> None:
        with telemetry_env(AWS_SAA_TELEMETRY_URL=unreachable_url()):
            with mock.patch.object(Telemetry, "_start_flush", lambda self: None):
                memory = StudyMemory(self.database)
                memory.start_session("learner-01", "s-1", "same-event", "quiz", "custom", 5)
                memory.start_session("learner-01", "s-2", "same-event", "quiz", "custom", 5)
        started = [item for item in self.payloads() if item["event_type"] == "session_started"]
        self.assertEqual(len(started), 1)

    def test_rejected_batch_is_dropped_rather_than_wedging_the_queue(self) -> None:
        with stub_endpoint(status_code=422) as (_, url):
            with telemetry_env(AWS_SAA_TELEMETRY_URL=url):
                with mock.patch.object(Telemetry, "_start_flush", lambda self: None):
                    memory = StudyMemory(self.database)
                    self.run_session(memory)
                memory._telemetry.flush()
        self.assertEqual(self.outbox(), [])

    def test_server_error_keeps_events_for_a_later_retry(self) -> None:
        with stub_endpoint(status_code=503) as (_, url):
            with telemetry_env(AWS_SAA_TELEMETRY_URL=url):
                with mock.patch.object(Telemetry, "_start_flush", lambda self: None):
                    memory = StudyMemory(self.database)
                    self.run_session(memory)
                self.assertEqual(memory._telemetry.flush(), 0)
        self.assertEqual(len(self.outbox()), 2)

    def test_outbox_is_bounded_when_the_endpoint_stays_dead(self) -> None:
        with telemetry_env(AWS_SAA_TELEMETRY_URL=unreachable_url()):
            with mock.patch.object(Telemetry, "_start_flush", lambda self: None):
                memory = StudyMemory(self.database)
                self.run_session(memory)
                # Rows are discarded at the start of the flush that follows the last
                # permitted attempt, so this needs one more pass than MAX_ATTEMPTS.
                for _ in range(MAX_ATTEMPTS + 1):
                    memory._telemetry.flush()
        self.assertEqual(self.outbox(), [])


if __name__ == "__main__":
    unittest.main()
````
