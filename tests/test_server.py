from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_TEMP = tempfile.TemporaryDirectory()
os.environ["AWS_SAA_STUDY_DB"] = str(Path(SERVER_TEMP.name) / "server.sqlite3")
sys.path.insert(0, str(PROJECT_ROOT / "cert_coach" / "templates" / "study-memory-mcp"))

import server  # noqa: E402
from store import StudyMemory  # noqa: E402


def tearDownModule() -> None:
    SERVER_TEMP.cleanup()


class ServerProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        server.MEMORY = StudyMemory(Path(self.temp_dir.name) / "memory.sqlite3")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_initialize_and_tool_discovery(self) -> None:
        initialized = server.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}
        )
        listed = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(initialized["result"]["serverInfo"]["version"], "0.3.0")
        names = {tool["name"] for tool in listed["result"]["tools"]}
        self.assertEqual(len(names), 13)
        self.assertIn("start_study_session", names)
        self.assertIn("review_flashcard", names)
        attempt = next(tool for tool in listed["result"]["tools"] if tool["name"] == "record_quiz_attempt")
        self.assertEqual(
            attempt["inputSchema"]["required"], ["learner_id", "event_id", "topic_id", "correct"]
        )
        # A stray argument must not cost the caller a graded attempt.
        self.assertTrue(attempt["inputSchema"]["additionalProperties"])
        topic_id = attempt["inputSchema"]["properties"]["topic_id"]
        self.assertIn("3.2=", topic_id["description"])
        # An enum here would make a client drop a near-miss locally, showing the caller
        # nothing; the server answers with the valid IDs instead so it can retry.
        for field in ("topic_id", "task_id", "domain", "difficulty", "activity_type", "response_type"):
            self.assertNotIn("enum", attempt["inputSchema"]["properties"][field])

    def test_catalog_tool_returns_canonical_task(self) -> None:
        response = server.handle(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "get_exam_catalog", "arguments": {"task_id": "2.2"}},
            }
        )
        self.assertIn("Design highly available", response["result"]["content"][0]["text"])

    def call(self, name: str, arguments: dict) -> dict:
        response = server.handle(
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
        )
        return response["result"]

    def test_unknown_topic_id_is_an_mcp_error_that_lists_the_valid_ids(self) -> None:
        result = self.call(
            "record_quiz_attempt",
            {
                "learner_id": "learner",
                "event_id": "attempt-1",
                "task_id": "3.2",
                "topic_id": "ec2-instance-types",
                "correct": True,
            },
        )
        text = result["content"][0]["text"]
        self.assertTrue(result["isError"])
        self.assertIn("unknown topic_id 'ec2-instance-types'", text)
        self.assertIn("compute-selection", text)
        self.assertEqual(server.MEMORY.get_progress("learner")["total_attempts"], 0)

    def test_attempt_survives_stray_arguments_and_a_conflicting_parent(self) -> None:
        result = self.call(
            "record_quiz_attempt",
            {
                "learner_id": "learner",
                "event_id": "attempt-1",
                "domain": "cost-optimized",
                "task_id": "3.1",
                "topic_id": "compute-selection",
                "correct": "false",
                "selected_option": "B",
            },
        )
        payload = json.loads(result["content"][0]["text"])
        self.assertNotIn("isError", result)
        self.assertTrue(payload["recorded"])
        self.assertEqual(payload["task_id"], "3.2")
        self.assertEqual(payload["domain"], "high-performing")
        self.assertEqual(payload["ignored_arguments"], ["selected_option"])
        self.assertEqual(len(payload["corrections"]), 2)
        self.assertEqual(server.MEMORY.get_progress("learner")["total_attempts"], 1)

    def test_catalog_overview_exposes_the_task_to_topic_map(self) -> None:
        payload = json.loads(self.call("get_exam_catalog", {})["content"][0]["text"])
        tasks = [task for domain in payload["domains"] for task in domain["tasks"]]
        compute = next(task for task in tasks if task["id"] == "3.2")
        self.assertIn("compute-selection", compute["topic_ids"])
        self.assertTrue(all(task["topic_ids"] for task in tasks))

    def test_json_rpc_error_codes_and_null_id(self) -> None:
        invalid = server.handle([])
        missing_method = server.handle({"jsonrpc": "2.0", "id": 1})
        unknown = server.handle({"jsonrpc": "2.0", "id": None, "method": "unknown"})
        bad_params = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": []})
        self.assertEqual(invalid["error"]["code"], -32600)
        self.assertEqual(missing_method["error"]["code"], -32600)
        self.assertEqual(unknown["error"]["code"], -32601)
        self.assertIsNone(unknown["id"])
        self.assertEqual(bad_params["error"]["code"], -32602)

    def test_notification_is_silent_and_ping_works(self) -> None:
        self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertEqual(server.handle({"jsonrpc": "2.0", "id": 8, "method": "ping"})["result"], {})


if __name__ == "__main__":
    unittest.main()
