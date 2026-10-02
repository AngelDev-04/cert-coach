# Local study-memory MCP server

This standard-library Python server provides private, structured learner memory for the AWS SAA-C03 Study Coach. It stores study evidence, not chat transcripts or generated question text.

## Data location and migration

The default database is:

```text
~/.kiro/aws-saa-study-coach/study-memory.sqlite3
```

Override it with `AWS_SAA_STUDY_DB`. Schema upgrades are additive and automatic; v0.1 databases are migrated to SQLite `user_version = 2` without deleting profiles, attempts, or flashcards.

## MCP tools

- Catalog: `get_exam_catalog`
- Profile: `set_learner_profile`, `get_learner_profile`
- Sessions: `start_study_session`, `get_study_session`, `complete_study_session`
- Evidence: `record_quiz_attempt`, `get_progress`, `get_study_recommendation`
- Recall: `save_flashcard`, `get_due_flashcards`, `get_flashcard_answer`, `review_flashcard`

Mutation tools use caller-generated `event_id` values. Reusing an event ID when retrying the same action prevents duplicate attempts, cards, sessions, or reviews.

Due-card retrieval intentionally omits answers. The recall workflow asks the learner first, retrieves the answer second, and schedules Again/Hard/Good/Easy feedback third.

## What is stored

Profiles, canonical domain/task/topic IDs, activity and response types, correctness, optional timing/confidence/flags, concise misconceptions, scenario rubric scores, study-session metadata, flashcard content, and scheduling state. Scenario rubrics are reported separately from objective-question accuracy.

The server does **not** store conversations, generated question stems/options, or mock-exam answer text.

## What is transmitted

Nothing. The server makes no network calls.

## Local smoke test

```bash
AWS_SAA_STUDY_DB=/tmp/saa-study-test.sqlite3 python3 server.py
```

Send newline-delimited JSON-RPC requests such as `initialize`, `tools/list`, or `tools/call`. Recoverable tool validation failures use MCP `isError`; malformed JSON-RPC uses standard error codes.
