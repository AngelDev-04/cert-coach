# Study-memory v0.2 design

## Boundaries

The Power has five layers:

1. `docs/` defines current exam scope, canonical task/topic identifiers, content rules, and official references.
2. `POWER.md` and `steering/steering.md` carry the rules the agent must always follow, including the question presentation contract. Kiro copies only these and `mcp.json` on install, so a rule placed anywhere else never reaches the agent.
3. `skills/` defines learner-facing workflows and when MCP tools may be called.
4. `study-memory-mcp/server.py` is the JSON-RPC/MCP boundary and publishes constrained tool schemas.
5. `study-memory-mcp/store.py` owns validation, migrations, idempotency, analytics, recommendations, and SQLite access.

Question and chat text never crosses into persistence. The store retains only structured evidence needed to plan future study.

## Evidence model

Objective `quiz`, `diagnostic`, and `mock` attempts contribute to accuracy and mastery. `scenario` activity uses a 0–4 rubric and remains separate. Every new attempt uses canonical domain/task/topic IDs and a caller-generated event ID.

Mastery is a recency-weighted objective success rate with 90-day exponential decay; challenging evidence has more weight than standard evidence, and foundation evidence has less. Evidence labels are:

- `unsampled`: 0 attempts;
- `insufficient`: 1–2 attempts;
- `developing`: 3–7 attempts;
- `established`: 8 or more attempts.

These labels describe local practice evidence, not exam readiness.

## Recommendation order

1. If no objective evidence exists, run the 14-task diagnostic.
2. Sample untouched domains in official weight order.
3. Bring canonical tasks to at least three objective samples.
4. Target the lowest recency/difficulty-weighted task after a sample-size uncertainty adjustment.
5. Within that task, select the least-sampled/lowest-mastery canonical topic.
6. Allocate due flashcards and questions within the saved session length, then add deadline and weekly-session context.

No recommendation estimates a probability of passing.

## Session plans

- Diagnostic: 14 questions, one for every official task statement.
- Mini mock: 20 questions distributed by official domain weight.
- Full mock: 65 questions distributed by official domain weight.
- Custom quiz/mock: 1–65 questions.
- Scenario: one coached architecture evaluation by default.

Scores remain hidden in active-session responses. Coverage counts permit continuation without storing question text.

## Spaced recall

Due-card prompts exclude answers. After attempted recall, the answer can be fetched and the card rated Again, Hard, Good, or Easy. Scheduling is deterministic, bounded by an ease floor/ceiling, UTC-normalized, and idempotent by review event ID.

## SQLite migration

Initialization creates missing v0.2 tables, adds missing v0.2 columns to v0.1 tables, creates partial unique event indexes, and sets `PRAGMA user_version = 2`. Legacy attempts remain visible at domain level; only new canonical attempts can contribute to task/topic evidence.
