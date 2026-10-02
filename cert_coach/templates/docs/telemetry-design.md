# Adoption telemetry design

## Purpose and boundary

A team running this Power needs to know whether colleagues are using it. That question is
answerable from activity metadata alone, so this reports **that** a session happened and never
**how it went**. The distinction is the whole design: widening the payload would turn a usage
monitor into performance surveillance of colleagues, which is a different thing with different
consent requirements.

`learner_id` is excluded for the same reason. It adds nothing to an adoption count while
linking the monitor to the learner's study records.

## Payload

`PAYLOAD_FIELDS` in `study-memory-mcp/telemetry.py` is an allowlist applied when the payload is
built, after the caller's fields are merged. A caller passing `correct` or `topic_id` therefore
cannot widen what leaves the machine.

| Field | Source |
| --- | --- |
| `event_id` | `"{event_type}:{session_id}"` — the ingest primary key |
| `event_type` | `session_started` or `session_completed` |
| `install_id` | random UUID in `telemetry_state`, stable for the life of the database |
| `user_key` | `username@hostname`, or `AWS_SAA_TELEMETRY_USER` |
| `power_version` | `store.POWER_VERSION` |
| `activity_type`, `mode` | the session's own plan |
| `target_questions`, `questions_answered` | counts |
| `duration_seconds` | `completed_at - started_at` |
| `client_platform` | `platform.system()` |
| `occurred_at` | UTC ISO 8601 |

Never sent: correctness, accuracy, mastery, domain/task/topic IDs, difficulty, confidence,
misconceptions, scenario rubrics, flashcard prompts and answers, question text, chat.

## Configuration

`study-memory-mcp/telemetry_config.py` carries the deployed endpoint and bearer token as
committed constants. The team fills them in once and re-shares the Power; colleagues configure
nothing. While `TELEMETRY_ENDPOINT` is empty the Power transmits nothing.

This cannot live in `mcp.json`: `scripts/validate_project.py` rejects any `${` there, because
Kiro never expands `${PLUGIN_ROOT}` and expands real environment variables only after
`kiroAgent.mcpApprovedEnvVars` approval.

Environment variables exist only as escape hatches, never as required setup:

| Variable | Effect |
| --- | --- |
| `AWS_SAA_TELEMETRY_DISABLED=1` | Kill switch for one machine |
| `AWS_SAA_TELEMETRY_URL` | Override the endpoint (the test suite points this at a local stub) |
| `AWS_SAA_TELEMETRY_TOKEN` | Override the bearer token |
| `AWS_SAA_TELEMETRY_USER` | Override the reported identity |
| `AWS_SAA_TELEMETRY_TIMEOUT` | Request timeout, default 3s, capped at 30s |

Only `https://` endpoints are accepted, with one exception: loopback over plain `http://`, so
the test suite can run a stub without a certificate. Such a request never leaves the machine.

**The committed token is a spam gate, not a security boundary.** Anyone who can read the
repository can read it. That is tolerable only because the endpoint is write-only and the
payload carries no study performance data. Keep the repository private and throttle the API
stage.

## The agent cannot trigger it

Reporting happens inside `StudyMemory.start_session` and `StudyMemory.complete_session`. No MCP
tool maps to it and `MEMORY_HANDLERS` gains no entry, so the model has no verb to send, skip, or
fabricate a report. `tests/test_telemetry.py` asserts this against the live tool list.

`session_started` is the load-bearing event: a learner who abandons a session never reaches
`complete_session`, so adoption must not depend on completion. `session_completed` fires only on
the `NULL` → timestamp transition, so completing an already-complete session reports once.

## Delivery

Events are queued in `telemetry_outbox` in the learner's own SQLite database and flushed on a
background daemon thread, so:

- studying offline still counts — the backlog flushes when the laptop reconnects;
- an unreachable endpoint can never make a study action fail, block, or slow down.

Up to 50 events go per request. A 2xx deletes the batch. A connection error increments
`attempts` and leaves the rows for a later flush. A 4xx other than 408/429 also deletes them,
because it will not succeed on retry and one rejected event must not wedge the queue behind it.

An event queued while a flush is in flight sets a pending flag that the flush loop re-checks
before exiting, so `session_completed` is not held back to the next session.

Rows are discarded once `attempts` reaches 10 or they pass 30 days, on the following flush.
A permanently dead endpoint therefore cannot grow the learner's database.

## Storage

`telemetry_state` and `telemetry_outbox` live in the study-memory database and are created by
`Telemetry.ensure_schema` during `StudyMemory._initialize`. They are additive and outside the
learner-memory contract, so `SCHEMA_VERSION` stays at `2`; bumping it would wrongly imply the
study schema changed.
