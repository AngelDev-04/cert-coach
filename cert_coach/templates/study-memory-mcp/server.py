#!/usr/bin/env python3
"""Standard-library stdio MCP server for private SAA-C03 learner memory."""

from __future__ import annotations

import inspect
import json
import sys
import traceback
from typing import Any, Callable

from catalog import DOMAINS, TASKS, TOPICS, load_catalog
from store import (
    ACTIVITY_TYPES,
    CONFIDENCE_LEVELS,
    DIFFICULTIES,
    FLASHCARD_RATINGS,
    POWER_VERSION,
    RESPONSE_TYPES,
    RUBRIC_DIMENSIONS,
    StudyMemory,
)

SERVER_INFO = {"name": "aws-saa-study-memory", "version": POWER_VERSION}
MEMORY: StudyMemory | None = None


def memory() -> StudyMemory:
    """Open the store on first use so a storage fault surfaces as a tool error, not a dead server."""
    global MEMORY
    if MEMORY is None:
        MEMORY = StudyMemory()
    return MEMORY
DOMAIN_IDS = list(DOMAINS)
TASK_IDS = list(TASKS)
TOPIC_IDS = list(TOPICS)

LEARNER_ID = {"type": "string", "minLength": 1, "maxLength": 128}
EVENT_ID = {
    "type": "string",
    "minLength": 1,
    "maxLength": 128,
    "description": "Caller-generated unique event ID. Reuse it when retrying the same mutation.",
}
SESSION_ID = {"type": "string", "minLength": 1, "maxLength": 128}
TOPIC_ID_DESCRIPTION = "Canonical topic. Valid values per task_id: " + "; ".join(
    f"{task_id}={'|'.join(TASKS[task_id]['topic_ids'])}" for task_id in TASKS
)


def object_schema(
    properties: dict[str, Any], required: list[str] | None = None, *, strict: bool = False
) -> dict[str, Any]:
    """Build a tool input schema.

    Unknown properties are permitted by default: a client that validates arguments
    against this schema would otherwise reject an entire call over one stray key,
    and the dispatcher already drops arguments the handler does not accept.
    """
    schema: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": not strict}
    if required:
        schema["required"] = required
    return schema


RUBRIC_SCHEMA = object_schema(
    {dimension: {"type": "integer", "minimum": 0, "maximum": 4} for dimension in sorted(RUBRIC_DIMENSIONS)}
)

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_exam_catalog",
        "description": "Get canonical SAA-C03 domains, task statements, topic IDs, selection rules, and common confusions.",
        "inputSchema": object_schema(
            {
                "domain": {"type": "string", "enum": DOMAIN_IDS},
                "task_id": {"type": "string", "enum": TASK_IDS},
            }
        ),
    },
    {
        "name": "set_learner_profile",
        "description": "Create or partially update a learner's target date and study-time preferences.",
        "inputSchema": object_schema(
            {
                "learner_id": LEARNER_ID,
                "target_exam_date": {"type": "string", "format": "date"},
                "weekly_hours": {"type": "number", "exclusiveMinimum": 0, "maximum": 168},
                "session_minutes": {"type": "integer", "minimum": 5, "maximum": 480},
                "preferences": {"type": "string", "minLength": 1, "maxLength": 2000},
            },
            ["learner_id"],
        ),
    },
    {
        "name": "get_learner_profile",
        "description": "Retrieve a learner's saved study profile.",
        "inputSchema": object_schema({"learner_id": LEARNER_ID}, ["learner_id"]),
    },
    {
        "name": "start_study_session",
        "description": "Idempotently start a diagnostic, weighted mock, quiz, or scenario session and return its coverage plan.",
        "inputSchema": object_schema(
            {
                "learner_id": LEARNER_ID,
                "session_id": SESSION_ID,
                "event_id": EVENT_ID,
                "activity_type": {"type": "string", "enum": ["diagnostic", "mock", "quiz", "scenario"]},
                "mode": {"type": "string", "enum": ["diagnostic", "mini", "full", "custom"]},
                "target_questions": {"type": "integer", "minimum": 1, "maximum": 65},
            },
            ["learner_id", "session_id", "event_id", "activity_type", "mode"],
        ),
    },
    {
        "name": "get_study_session",
        "description": "Get session coverage and completion progress. Scores are withheld until completion.",
        "inputSchema": object_schema(
            {"learner_id": LEARNER_ID, "session_id": SESSION_ID}, ["learner_id", "session_id"]
        ),
    },
    {
        "name": "complete_study_session",
        "description": "Complete a study session and return its structured results and study-only disclaimer.",
        "inputSchema": object_schema(
            {"learner_id": LEARNER_ID, "session_id": SESSION_ID}, ["learner_id", "session_id"]
        ),
    },
    {
        "name": "record_quiz_attempt",
        "description": (
            "Idempotently record one objective question or separately scored scenario evaluation "
            "without storing question text. Supply topic_id: it determines task_id and domain, so "
            "those are optional and any conflicting value is corrected rather than rejected. "
            "activity_type defaults to the named session's activity."
        ),
        "inputSchema": object_schema(
            {
                "learner_id": LEARNER_ID,
                "event_id": EVENT_ID,
                "topic_id": {"type": "string", "description": TOPIC_ID_DESCRIPTION},
                "task_id": {
                    "type": "string",
                    "description": "One of: " + ", ".join(TASK_IDS) + ". Inferred from topic_id when omitted.",
                },
                "domain": {
                    "type": "string",
                    "description": "One of: " + ", ".join(DOMAIN_IDS) + ". Inferred from task_id when omitted.",
                },
                "topic": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 200,
                    "description": "Optional short label. Defaults to the catalog name for topic_id.",
                },
                "difficulty": {
                    "type": "string",
                    "description": "One of: " + ", ".join(sorted(DIFFICULTIES)) + ". Defaults to standard.",
                },
                "activity_type": {
                    "type": "string",
                    "description": "One of: " + ", ".join(sorted(ACTIVITY_TYPES))
                    + ". Defaults to the activity of the named session.",
                },
                "session_id": SESSION_ID,
                "question_id": {"type": "string", "minLength": 1, "maxLength": 128},
                "response_type": {
                    "type": "string",
                    "description": "One of: " + ", ".join(sorted(RESPONSE_TYPES))
                    + ". Defaults to the type required by activity_type.",
                },
                "correct": {"type": "boolean"},
                "time_spent_seconds": {"type": "integer", "minimum": 1, "maximum": 86400},
                "confidence": {
                    "type": "string",
                    "description": "One of: " + ", ".join(sorted(CONFIDENCE_LEVELS)) + ".",
                },
                "flagged": {"type": "boolean"},
                "misconception": {"type": "string", "minLength": 1, "maxLength": 500},
                "rubric": RUBRIC_SCHEMA,
                "occurred_at": {"type": "string", "format": "date-time"},
            },
            ["learner_id", "event_id", "topic_id", "correct"],
        ),
    },
    {
        "name": "get_progress",
        "description": "Summarize objective mastery by domain/task/topic and scenario rubrics separately, with evidence calibration.",
        "inputSchema": object_schema({"learner_id": LEARNER_ID}, ["learner_id"]),
    },
    {
        "name": "get_study_recommendation",
        "description": "Build a profile-, deadline-, due-card-, recency-, difficulty-, and sample-aware next study session.",
        "inputSchema": object_schema({"learner_id": LEARNER_ID}, ["learner_id"]),
    },
    {
        "name": "save_flashcard",
        "description": "Idempotently save a learner-owned recall card. Its answer is excluded from due-card prompts.",
        "inputSchema": object_schema(
            {
                "learner_id": LEARNER_ID,
                "event_id": EVENT_ID,
                "topic_id": {"type": "string", "description": TOPIC_ID_DESCRIPTION},
                "task_id": {
                    "type": "string",
                    "description": "One of: " + ", ".join(TASK_IDS) + ". Inferred from topic_id when omitted.",
                },
                "topic": {"type": "string", "minLength": 1, "maxLength": 200},
                "prompt": {"type": "string", "minLength": 1, "maxLength": 2000},
                "answer": {"type": "string", "minLength": 1, "maxLength": 4000},
                "due_at": {"type": "string", "format": "date-time"},
            },
            ["learner_id", "event_id", "topic", "prompt", "answer"],
        ),
    },
    {
        "name": "get_due_flashcards",
        "description": "List due recall prompts without answers so the learner must retrieve before review.",
        "inputSchema": object_schema(
            {
                "learner_id": LEARNER_ID,
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                "as_of": {"type": "string", "format": "date-time"},
            },
            ["learner_id"],
        ),
    },
    {
        "name": "get_flashcard_answer",
        "description": "Retrieve one card answer only after the learner has attempted recall.",
        "inputSchema": object_schema(
            {
                "learner_id": LEARNER_ID,
                "flashcard_id": {"type": "integer", "minimum": 1},
            },
            ["learner_id", "flashcard_id"],
        ),
    },
    {
        "name": "review_flashcard",
        "description": "Idempotently grade recall as Again/Hard/Good/Easy and schedule the next spaced review.",
        "inputSchema": object_schema(
            {
                "learner_id": LEARNER_ID,
                "flashcard_id": {"type": "integer", "minimum": 1},
                "event_id": EVENT_ID,
                "rating": {"type": "string", "enum": sorted(FLASHCARD_RATINGS)},
                "reviewed_at": {"type": "string", "format": "date-time"},
            },
            ["learner_id", "flashcard_id", "event_id", "rating"],
        ),
    },
]


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def result_text(value: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, indent=2)}]}


def tool_error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def get_exam_catalog(domain: str | None = None, task_id: str | None = None) -> dict[str, Any]:
    if domain is not None and domain not in DOMAINS:
        raise ValueError(f"unknown domain: {domain}")
    if task_id is not None and task_id not in TASKS:
        raise ValueError(f"unknown task_id: {task_id}")
    if task_id is not None:
        task = TASKS[task_id]
        if domain is not None and task["domain"] != domain:
            raise ValueError(f"task_id {task_id} does not belong to domain {domain}")
        return {
            "schema_version": load_catalog()["schema_version"],
            "domain": DOMAINS[task["domain"]],
            "task": task,
        }
    if domain is not None:
        catalog_domain = next(item for item in load_catalog()["domains"] if item["id"] == domain)
        return {"schema_version": load_catalog()["schema_version"], "domain": catalog_domain}
    return {
        "schema_version": load_catalog()["schema_version"],
        "exam_code": load_catalog()["exam_code"],
        "verified_on": load_catalog()["verified_on"],
        "domains": [
            {
                "id": item["id"],
                "name": item["name"],
                "weight": item["weight"],
                "tasks": [
                    {
                        "id": task["id"],
                        "name": task["name"],
                        "topic_ids": [topic["id"] for topic in task["topics"]],
                    }
                    for task in item["tasks"]
                ],
            }
            for item in load_catalog()["domains"]
        ],
    }


MEMORY_HANDLERS = {
    "set_learner_profile": "set_profile",
    "get_learner_profile": "get_profile",
    "start_study_session": "start_session",
    "get_study_session": "get_session",
    "complete_study_session": "complete_session",
    "record_quiz_attempt": "record_attempt",
    "get_progress": "get_progress",
    "get_study_recommendation": "get_recommendation",
    "save_flashcard": "save_flashcard",
    "get_due_flashcards": "get_due_flashcards",
    "get_flashcard_answer": "get_flashcard_answer",
    "review_flashcard": "review_flashcard",
}


def resolve_handler(name: str) -> Callable[..., Any]:
    if name == "get_exam_catalog":
        return get_exam_catalog
    if name not in MEMORY_HANDLERS:
        raise ValueError(f"unknown tool: {name}")
    return getattr(memory(), MEMORY_HANDLERS[name])


def dispatch_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    handler = resolve_handler(name)
    accepted = set(inspect.signature(handler).parameters)
    ignored = sorted(key for key in arguments if key not in accepted)
    payload = handler(**{key: value for key, value in arguments.items() if key in accepted})
    if ignored and isinstance(payload, dict):
        payload = {**payload, "ignored_arguments": ignored}
    return result_text(payload)


def _require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise JsonRpcError(-32602, f"{name} must be an object")
    return value


def handle(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return {"jsonrpc": "2.0", "id": message.get("id") if isinstance(message, dict) else None, "error": {"code": -32600, "message": "Invalid Request"}}
    is_notification = "id" not in message
    request_id = message.get("id")
    method = message["method"]
    if is_notification:
        return None
    try:
        if method == "initialize":
            params = _require_object(message.get("params", {}), "params")
            payload: Any = {
                "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            }
        elif method == "ping":
            payload = {}
        elif method == "tools/list":
            payload = {"tools": TOOLS}
        elif method == "tools/call":
            params = _require_object(message.get("params"), "params")
            name = params.get("name")
            if not isinstance(name, str) or not name:
                raise JsonRpcError(-32602, "params.name must be a non-empty string")
            arguments = _require_object(params.get("arguments", {}), "params.arguments")
            try:
                payload = dispatch_tool(name, arguments)
            except (TypeError, ValueError) as error:
                payload = tool_error(str(error))
        else:
            raise JsonRpcError(-32601, "Method not found")
        return {"jsonrpc": "2.0", "id": request_id, "result": payload}
    except JsonRpcError as error:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": error.code, "message": error.message}}
    except Exception as error:
        traceback.print_exc(file=sys.stderr)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32603, "message": f"Internal error: {type(error).__name__}: {error}"},
        }


def main() -> None:
    print(f"study-memory {SERVER_INFO['version']} ready on stdio", file=sys.stderr, flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = handle(message)
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        except Exception as error:  # never let one malformed message end the session
            traceback.print_exc(file=sys.stderr)
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": f"Internal error: {type(error).__name__}: {error}"},
            }
        if response is None:
            continue
        try:
            print(json.dumps(response, ensure_ascii=False), flush=True)
        except (BrokenPipeError, ValueError):
            break
        except TypeError:
            traceback.print_exc(file=sys.stderr)
            print(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": response.get("id"),
                        "error": {"code": -32603, "message": "Internal error: result was not serializable"},
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
