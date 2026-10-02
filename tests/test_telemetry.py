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
                    learner_id="miguel",
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
