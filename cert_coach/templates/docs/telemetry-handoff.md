# Adoption telemetry — handoff

**Status as of 2026-09-01.** Written so another agent (or another person) can pick this up cold.
Code is complete and green in both repositories. What remains is AWS deployment, which needs a
human with console access.

Design rationale lives in [`telemetry-design.md`](telemetry-design.md); this file is the
build log and the to-do list. Read both before changing anything.

---

## 1. What this is

The Study Coach Power stores everything locally in
`~/.kiro/aws-saa-study-coach/study-memory.sqlite3`, so there was no way to tell whether
colleagues who installed it are actually studying. DevOps wanted that answer centrally, in
MySQL on RDS.

It is an **adoption monitor, not a performance monitor.** "Is anyone using this?" is fully
answerable from activity metadata, so no study performance data is ever transmitted.

Two repositories:

| Repository | Role | State |
| --- | --- | --- |
| `aws-saa-study-coach` (this one) | Kiro Power. Queues and sends events. | 44 tests pass, `validate_project.py` passes, **committed** in `39f5205` |
| `../study-hub` | Chalice ingest API → RDS MySQL. | 38 tests pass, 95.71% coverage, ruff clean, **not yet a git repo** |

```
Power repo                              study-hub
                                        (copier from ztech-lambda-base, api + mysql)
 store.py start_session/
 complete_session
      │ (in-process, guarded, after commit)
      ▼
 telemetry.py  ──HTTPS──▶  API Gateway ─▶ Chalice app
 stdlib urllib             (URL committed     routes → middlewares → handlers
 SQLite outbox              in the Power)     → domain → repositories → adapters
 background daemon thread                            │
                                              RDS MySQL (private subnets)
```

---

## 2. Four constraints that shaped every decision

Do not "clean up" code in a way that breaks these. Each one is load-bearing and each is pinned
by a test.

1. **The AI agent must never trigger the upload.** Emission is a side effect of the
   deterministic session actions in `store.py`. **No MCP tool exists for telemetry**, so the
   model has no verb with which to send, skip, or fabricate a report.
   Pinned by `test_no_mcp_tool_can_send_telemetry` (asserts exactly 13 tools, none matching
   telemetry/sync/upload verbs).
2. **Zero configuration for colleagues.** No env var, no `mcp.json` edit, no config file to
   drop in. The endpoint ships as committed constants in `study-memory-mcp/telemetry_config.py`.
3. **No study performance data on the wire, ever.** Enforced three times over: an allowlist in
   the client, Cerberus rejecting unknown keys server-side, and a MySQL table that has no
   column to hold it.
4. **Telemetry must never break studying.** Every failure path is silent and off the calling
   thread. An unreachable endpoint cannot make a study action fail, block, or slow down.

---

## 3. Repo 1 — the Power (complete)

### New files

| File | What it does |
| --- | --- |
| `study-memory-mcp/telemetry.py` | The whole client: outbox schema, allowlist filter, background flush, retry/bounding, the two event builders. **stdlib only** — the Power keeps its dependency-free install. |
| `study-memory-mcp/telemetry_config.py` | Two committed constants: `TELEMETRY_ENDPOINT`, `TELEMETRY_TOKEN`. Both empty → the Power is **inert** and transmits nothing. |
| `tests/test_telemetry.py` | 15 tests. `unittest` + `tempfile` + `http.server`, matching existing conventions; no new test dependencies. |
| `docs/telemetry-design.md` | Payload contract, outbox/retry semantics, kill switch, threat model. |

### Why the endpoint is a Python constant and not `mcp.json`

`scripts/validate_project.py:106` rejects any `${` in `mcp.json` args or env values. Kiro never
expands `${PLUGIN_ROOT}`, and expands real environment variables only after the user approves
them through `kiroAgent.mcpApprovedEnvVars` — which is manual configuration, i.e. exactly what
constraint 2 forbids. A committed Python constant sidesteps both.

### Modified: `study-memory-mcp/store.py` — four touch points

```
line  17   from telemetry import Telemetry
line  19   POWER_VERSION = "0.3.0"          # server.py now imports this for SERVER_INFO
line 185   __init__      → self._telemetry = Telemetry(self.database_path, ...)
line 188   _emit()       → guarded helper; swallows everything
line 543   start_session → emits after commit, on the NON-duplicate path only
line 637   complete_session → emits only on the NULL → timestamp transition
```

`_initialize` also calls `Telemetry.ensure_schema(connection)`.

**`SCHEMA_VERSION` stays `2` deliberately.** The telemetry tables are additive and sit outside
the learner-memory contract; bumping it would wrongly imply the study schema changed, and
`tests/test_memory.py:255` asserts against the constant.

### Data contract

Allowlisted in `PAYLOAD_FIELDS` and filtered **last**, so a future caller cannot widen the
payload by passing extra keys to `record()`.

**Sent:** `event_id` (`"{event_type}:{session_id}"`, the idempotency key), `event_type`
(`session_started` | `session_completed`), `install_id` (UUID, stable per database), `user_key`
(`username@hostname`), `power_version`, `activity_type`, `mode`, `target_questions`,
`questions_answered`, `duration_seconds`, `client_platform`, `occurred_at`.

**Never sent:** `correct`, accuracy, mastery, `domain`, `task_id`, `topic_id`, `difficulty`,
`confidence`, `misconception`, scenario rubrics, flashcard prompt/answer — and `learner_id`,
which adds nothing to an adoption count while linking this monitor to the learner's study
records.

`session_started` is the load-bearing event: a learner who abandons a session never calls
`complete_study_session`, so adoption must not depend on completion.

### Behaviour worth knowing before you touch it

- `enabled` requires `https://` **or** a loopback `http://` prefix. The loopback carve-out
  exists so the tests can run a stub endpoint without a certificate; such a request never
  leaves the machine.
- `_start_flush` / `_flush_quietly` use a `_flushing` + `_pending` pair. **This is a bug fix,
  not decoration.** Without `_pending`, an event queued while a flush is in flight was silently
  dropped, so `session_completed` arrived a session late. A test covers it.
- `_post` returns `True` for 2xx **and** for 4xx other than 408/429 — a permanently rejected
  event is dropped rather than left to wedge the queue behind it.
- `_discard_exhausted` runs at the *start* of `flush()`, so a row at `attempts == MAX_ATTEMPTS`
  survives until the following flush. That is intended; the test loops `MAX_ATTEMPTS + 1` times
  because of it.
- Escape hatches, never required setup: `AWS_SAA_TELEMETRY_DISABLED=1` (kill switch),
  `AWS_SAA_TELEMETRY_URL` / `_TOKEN` / `_USER` / `_TIMEOUT` (overrides, used by tests).

### Documentation corrected

Default-on network egress contradicted claims already committed in the repo. Fixing them was
part of the change, not a follow-up: `README.md` (the "no network service is required" claim,
plus a new "Team adoption telemetry" section with a sent / never-sent table), `POWER.md`
(Privacy Contract + "Adoption reporting"), `study-memory-mcp/README.md` ("What is transmitted").

`tests/test_project.py:83` asserts exact privacy strings about *question text* — those stay
true and were left intact.

---

## 4. Repo 2 — `study-hub` (complete, not deployed)

Scaffolded with the real template, not by hand:

```bash
copier copy --trust --vcs-ref=HEAD --defaults \
  --data project_name=study-hub --data project_type=api \
  --data use_mysql=true --data use_mongodb=false \
  /home/ing-miguel-j/Repositorios/chalice-lambda/ztech-lambda-base <dest>
```

Its conventions, **not** the Power's: ruff single quotes / 120 cols, pytest at
`--cov-fail-under=80`. The template's structure is preserved throughout — routes → handlers →
domain → repositories → adapters, `ServiceResult` / `ResultState`, `BaseHandler`,
`RepositoryContext`.

### API surface

`prefix = '/v1/study-telemetry'` — `GET /health`, `POST /events` (write-only; nothing is ever
read back through the API).

Auth is `Authorization: Bearer <INGEST_TOKEN>`, compared with `hmac.compare_digest` on bytes.
503 when `INGEST_TOKEN` is unset, 401 on mismatch.

### Five deviations from the company template

The first four are **defects found in `ztech-lambda-base`**. They will recur in every service
scaffolded from it, so they are worth reporting upstream.

| Template | Here | Why |
| --- | --- | --- |
| `suprautils` from Bitbucket | `pymysql`, `cerberus`, stdlib | Dependencies via uv; drops the private build dependency |
| `IBaseRepository(metaclass=SingletonMeta)` | plain class | A cached repository pins an adapter whose MySQL connection is already closed by the time a warm container serves its next request |
| `BaseHandler._execute` returns a `ServiceResult` | returns `(code, body)` | The template's own routes already unpack a 2-tuple; `domain/results.as_response` supplies the mapping the template is missing |
| `IHealthAdapter` imported, never defined | defined in `database/__init__.py` | The template as scaffolded **cannot import**: `adapters/mysql.py` imports a name that `database/__init__.py` does not export |
| `CORSConfig(allow_origin=CORS_ORIGINS, allow_credentials=True)` | applied only when `CORS_ORIGINS` is set; credentials off | `''` is not a valid origin, and `Allow-Origin: *` with `Allow-Credentials: true` is refused by every browser. This API authenticates with a bearer header, not cookies |

`suprautils` replacements: `ZValidator` → `cerberus` (the template's rule dicts are already
Cerberus format), `ConfigManager` → `core/config.py` over `os.environ`, `SingletonMeta` → an
~8-line local metaclass, `ZMongo` → `adapters/zmysql.py` (`parse_uri` + a `ZMysql` context
manager that commits on clean exit, rolls back on exception, always closes), `helpers.debug.log`
→ stdlib `logging`.

### Schema — `src/migrations/0001_study_activity.sql`

`study_activity`, primary key `event_id VARCHAR(128)` so replays upsert instead of inflating
anyone's session count. InnoDB / utf8mb4, `received_at` default `CURRENT_TIMESTAMP`.
**The table has no column for study performance data** — the schema is the last line of the
privacy contract.

Two views are what DevOps actually queries:

- `v_user_activity` — per `user_key`: first seen, last seen, sessions started/completed, total
  study minutes, days since last session.
- `v_weekly_adoption` — per ISO week: distinct users, distinct installs, sessions completed.

The upsert uses MySQL 8.0.19+ row-alias syntax (`... AS new ON DUPLICATE KEY UPDATE`), not the
deprecated `VALUES()` function. It carries a `# noqa: S608` on the **closing** `"""` line —
putting it on the opening line injects the comment into the SQL string itself. That mistake was
made once here; the guard is `assert 'noqa' not in UPSERT`.

### Cross-repo contract test

`tests/integration/test_client_contract.py` imports the Power's `telemetry.py` and asserts the
wire format matches the Cerberus schema. It `skipif`s on `STUDY_COACH_PATH` being unset.

**This is the only guard against the two repos drifting apart.** If you change
`PAYLOAD_FIELDS`, `EVENT_TYPES`, or `BATCH_SIZE` on one side, this test is what tells you the
other side needs the same change. Run it with:

```bash
STUDY_COACH_PATH=/home/ing-miguel-j/Repositorios/aws-saa-study-coach uv run pytest
```

---

## 5. What is left

Everything below needs AWS console access or a human decision. Nothing is blocked on code.

### 5.1 Before anything else — tell the team

The monitor names individual colleagues (`username@hostname`) and is **on by default with no
opt-in step** once the endpoint is filled in. Tell people it is running before sharing the
build. The kill switch (`AWS_SAA_TELEMETRY_DISABLED=1`) is the honest counterpart to that, and
it is worth naming explicitly when you announce it.

### 5.2 Put the ingest repo under version control

It is currently a plain directory. `git init`, first commit, push to wherever company Lambda
repos live.

### 5.3 AWS

1. **RDS MySQL 8.0**, `db.t4g.micro`, Single-AZ, 20 GB gp3, **public access off**
   (~$12–15/month). 8.0.19 or newer — the upsert uses row-alias syntax.
2. **Security groups:** `rds-sg` allows 3306 **only** from the Lambda's security group.
3. Run `src/migrations/0001_study_activity.sql` against the new database.
4. **Deploy with Chalice**, Lambda attached to the VPC private subnets.
5. **Lambda env vars:** `MYSQL_URI`, `INGEST_TOKEN`. See `.env.example`. Leave `CORS_ORIGINS`
   empty — the client is a Python MCP server, it sends no `Origin` and never preflights.
6. If you source credentials from Secrets Manager, add an **interface VPC endpoint** for it. A
   VPC-attached Lambda has no internet route, and this avoids paying for a NAT gateway to fetch
   one secret.
7. **Enable API Gateway stage throttling.** Non-optional: the bearer token is committed in the
   Power repository, so it is a spam gate, not a security boundary. Keep the Power repo private.

### 5.4 Close the loop

Paste the deployed URL and token into `study-memory-mcp/telemetry_config.py`:

```python
TELEMETRY_ENDPOINT = "https://<api-id>.execute-api.<region>.amazonaws.com/api/v1/study-telemetry/events"
TELEMETRY_TOKEN = "<the same value as INGEST_TOKEN>"
```

Commit, re-share the Power. Colleagues do nothing.

### 5.5 End-to-end verification

1. **Agent cannot send** — `tools/list` on the MCP server shows 13 tools, none telemetry.
2. **Local stub** — point `AWS_SAA_TELEMETRY_URL` at a local stub, run a diagnostic through the
   MCP tools, confirm both events arrive and the outbox drains.
3. **Against AWS** — `curl -X POST -H "Authorization: Bearer …" -d @sample.json <url>` → 201.
   Re-POST the identical payload and confirm the row count does not change.
4. **Reporting** — `SELECT * FROM v_user_activity ORDER BY last_seen DESC;`
5. **Offline** — block the endpoint, run a session, confirm it completes normally, then confirm
   it flushes once the endpoint returns.
6. **Kill switch** — `AWS_SAA_TELEMETRY_DISABLED=1`, confirm nothing is queued or sent.

---

## 6. Commands

```bash
# Power
cd /home/ing-miguel-j/Repositorios/aws-saa-study-coach
python3 scripts/validate_project.py            # → Validated Power v0.3.0: 4 domains, 14 tasks…
python3 -m unittest discover -s tests -v       # → Ran 44 tests … OK

# Ingest
cd /home/ing-miguel-j/Repositorios/study-hub
uv run pytest                                  # → 38 passed, 95.71% coverage
uv run ruff check .
chalice local                                  # exercise the routes
```

---

## 7. Notes for whoever picks this up

- **Do not add an MCP tool for telemetry**, however convenient it looks. Constraint 1 is the
  reason this design is acceptable at all, and `test_no_mcp_tool_can_send_telemetry` will fail.
- **Do not add fields to `PAYLOAD_FIELDS` without checking the never-sent list.** The client
  allowlist, the Cerberus schema, and the MySQL columns must be changed together, and the
  contract test is what enforces that.
- One observed oddity, benign: calling `flush()` manually while the background thread is also
  running can POST the same batch twice, because the outbox read-then-delete is not
  transactional. It does not happen in production — the `_flushing` lock permits one flusher —
  and the idempotent upsert absorbs it either way. Worth knowing before it surprises you in a
  debug script.
- `test_cors.py` deliberately has no `importlib.reload` test. Reloading `app` re-registers the
  Chalice `Blueprint`, which repoints its `_current_app` and makes the *original* app's
  `current_request` return `None` — it silently broke five unrelated route tests. The logic
  lives in the pure `build_cors_config`, which is fully covered instead.
