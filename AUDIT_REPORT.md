# ZKTeco ADMS Platform — Integral Audit Report

**Role:** Senior Software Auditor / Security Engineer / QA Lead / Architecture Reviewer
**Date (UTC):** 2026-09-10
**Rule of engagement:** read-only audit. No project file was modified; this report is the sole artifact created.
**System under audit:** FastAPI ADMS gateway + admin API + Next.js frontend, target device ZKTeco SpeedFace-V5LP.
**Reference:** `athwari/laravel-zkteco-adms-server` (functional protocol reference) + `ARCHITECTURE.md` + `docs/` + master prompt (§0–§108).

---

## 1. Executive Summary

The backend is a genuinely well-structured, idiomatic Python implementation (not a mechanical Laravel port): pure parsers, whitelisted command builders, per-endpoint RBAC, RS256 JWT with rotation/revocation, Argon2id, raw-payload preservation, ATTLOG idempotency, and `SKIP LOCKED` draining. Static gates pass: **78 tests green, 91.61% coverage, ruff clean, mypy-strict clean, FastAPI 0.141.1 exact**.

However the audit finds **4 HIGH findings** that block acceptance: (1) rate limiting is configured but never enforced — login/refresh and ADMS are unthrottled; (2) there is **no admin-user provisioning path** (no endpoint/CLI; `users.write/delete` are dead permissions), so RBAC cannot be operated and bootstrap requires hand-written DB rows; (3) **Alembic is broken by layout**: versions live in root `alembic/versions/` while the configured script location (`backend/alembic/`, and the Docker image copy) contains only `env.py` — `alembic upgrade head` is a silent no-op, so a fresh deploy starts with an empty database; (4) CI does not enforce what it claims — `mypy backend/app` runs from the repo root where no mypy config exists (defaults, not strict), and the frontend job cannot succeed (`npm ci` with no lockfile).

No CRITICAL findings (no RCE, no shell path, no SQLi, no JWT confusion, no secret leakage). The frontend is scaffold-only (2/10), and **real-device validation against a SpeedFace-V5LP was not performed and is not claimed — ADMS REAL DEVICE VALIDATION = NOT VERIFIED**.

**Verdict: FAIL** (HIGH findings pending, no CRITICALs). **Overall score: 66/100.**

---

## 2. Audit Scope

Inspected 100%: `backend/app` (63 source files), `backend/tests` (11 test files + 8 fixtures), root `alembic/versions/0001_initial.py`, `backend/alembic/env.py`, `docker-compose.yml`, both Dockerfiles, `backend/.env.example`, `frontend/` (14 files), `ARCHITECTURE.md`, all 5 `docs/`, `README.md`, CI workflow, `pyproject.toml`/`package.json`. Out of scope: live SpeedFace-V5LP traffic (no device available), PostgreSQL/Redis-backed execution (no servers in this environment), `npm` checks (no Node available).

## 3. Environment

| Component | Expected | Actual (measured) | Result |
|---|---|---|---|
| Python | 3.12+ | 3.14.4 runtime; Docker pins 3.12-slim; CI uses 3.12 | PASS |
| FastAPI | 0.141.1 | **0.141.1 installed** (`pip list`) | PASS |
| SQLAlchemy / asyncpg / Alembic | 2.x async / asyncpg / Alembic | 2.0.52 / 0.31.0 / 1.19.2 | PASS |
| Redis / Celery / structlog / jose / argon2 | present | 6.4.0 / 5.6.3 / 26.1.0 / python-jose 3.5.0 / argon2-cffi 25.1.0 | PASS |
| pydantic / settings / pytest / ruff / mypy / httpx | present | 2.13.5 / 2.15.0 / 9.1.1 / 0.16.7 / 2.3.1 / 0.28.1 | PASS |
| Next.js / React / TS / Node | declared | package.json declares Next 14.2.5 / React 18.3.1 / TS 5.5.4; **Node absent here → install/build/typecheck UNVERIFIED** | UNVERIFIED |
| PostgreSQL / Redis servers | — | absent in this environment → PG-backed paths UNVERIFIED | UNVERIFIED |

Inventory: 5 ADMS paths (8 ops), 16 admin ops, 12 tables in migration, 1 migration, 7 services, 6 repositories, 4 pure ADMS modules, 78 tests, 8 raw fixtures, 14 frontend files (8 stub pages).

## 4. Architecture Compliance — 8/10 (PASS with notes)

Separation is genuinely clean: `api/adms → services → repositories → models`; `adms/parser.py` + `adms/commands.py` are pure (no I/O); no SQL in routers (all ORM-bound, parameterised); no business logic in models; no circular imports; no blocking I/O in the event loop (only small PEM-file reads in `config.py:53,59`, see L-04). No `requests`/`time.sleep`/sync Redis usage found.

Notes (LOW): `api/v1/resources.py` bundles 5 routers in one 262-line file (layout shims re-export from it — works, but §5's per-resource files are 2-line shims); function-level lazy imports (`resources.py:114,167`, `devices.py:201`, `main.py:62,73`, `auth.py:43,46`); dead code (`new_request_id`, `body_preview` unused in prod, `cancel_command`/`expire_commands` unexposed, no-op Celery stub); module docstring in `services/command.py:3-5` claims "MAX+1 under row lock" while `queue_command` takes no lock (M-08).

## 5. ADMS Protocol Compliance — 8/10 (CODE PASS / DEVICE UNVERIFIED)

Against the Laravel reference (`routes/adms.php`, `AdmsController`, `AttendanceParser`, `CommandManager`, `DeviceManager`, `ValidateDeviceRequest`, DTOs/Enums/Events, migrations, Feature/Unit tests — all re-read for this audit):

- Routes: all five endpoints exist with correct methods (`api_route GET+POST /cdata`, `GET+POST /registry`, `GET /getrequest`, `POST /devicecmd`, `GET /inspect`). SN validation identical (`^[A-Za-z0-9_-]{1,64}$`, 400 paths identical). 413 body cap (10 MB, header + real-size checks), 503 device-limit, idempotent register-then-touch on every request — all match.
- ATTLOG: `UserID/Timestamp` minimum, `status/verify_mode/work_code` defaults, `Y-m-d H:i:s` + epoch, malformed lines skipped without aborting the batch (tested), `OK: N` wire ack. USERINFO `PIN/Name/Privilege/Card/Password`, PIN-less skip. Registry `,`-separated `~`-prefixed KV. Device-info `\n` KV + normalized-column sync. OPERLOG → `OK`. devicecmd batched + shell/multiline formats with per-ID flush. Wire `C:<id>:<cmd>\n`. `DATA UPDATE USERINFO` (not `USER ADD`), `DATA DELETE USERINFO` (not `DATA DEL`), 16-key GET OPTION whitelist, SHELL absent everywhere (only docstring mentions of the shell *result format*). Online derived from `last_activity_at`/120 s; no physical eviction. Deductions in §§17–18.
- Divergences found vs reference are intentional and documented (UUID PKs, `adms_payloads`, dedup constraint, `SKIP LOCKED`, no eviction) — accepted.

## 6. Database Audit — 8/10

- Tables (migration `0001_initial.py:17-194` vs spec §§7–23): all 12 present (`users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `devices`, `device_users`, `attendance_logs`, `adms_payloads`, `device_commands`, `device_events`, `audit_logs`), FKs with correct `CASCADE`/`SET NULL`, `UNIQUE(serial_number)`, `UNIQUE(device_id,pin)`, dedup `UNIQUE(device_id,pin,recorded_at,status,verify_mode,work_code)`, CHECKs on device/command status. Content matches models 1:1.
- Types: native `UUID`/`JSONB`/`INET`/`TIMESTAMPTZ`, `SmallInteger` for status/verify, no `VARCHAR`-for-everything. Indexes cover §24 (serial unique, status, last_activity, attendance device/pin/recorded/composite, commands device/status/proto, events device/type/created, audit user/device/created, payloads device/received).
- Deductions: redundant `ix_attendance_device_recorded_desc` (plain btree serves DESC scans) and `ix_cmd_device_proto` (duplicates the unique-constraint backing index) — L-02; `DeviceEvent.id` has no UUID default (relies on caller) — L-02; raw-SQL migration with `IF NOT EXISTS` masks drift and defeats autogenerate diffing — L-05; migration never executed against real PG in this environment — §18 UNVERIFIED (INFO).

## 7. Authentication Audit — 6/10

Argon2id default params (`security.py:20`), no bcrypt/MD5/SHA1 anywhere; RS256-only (`algorithms=[ALGORITHM]`, confusion/HS256/`alg=none` negative-tested); claims `sub/iat/exp/jti/type/iss/aud` enforced incl. issuer/audience/type; refresh rotation with revocation; uniform "Invalid credentials"; no passwords in logs/responses (sanitizer + verified by grep). Deductions: **no user provisioning (H-02)**; logout revokes refresh only, access token survives up to 15 min (M-01); no brute-force/lockout protection (H-01); revocation silently falls back to process memory without shared Redis (M-01); login 401s misleadingly when keys unconfigured (INFO).

## 8. Authorization / RBAC — 7/10

Every admin endpoint enforces `require_permission(...)` (verified per route; 403-tested for viewer); superuser bypass is explicit; permissions derived from join query; no RBAC in frontend only (frontend has no gating at all — backend remains source of truth, verified by 403 test). Single-tenant design: any permission holder can access any object UUID — no IDOR in the single-org threat model (INFO, document assumption). Deductions: `users.write/users.delete/devices.delete/attendance.export` are dead codes with no endpoints (H-02); no user CRUD to attach them to.

## 9. Security Audit — 6/10

- Injection: no raw SQL/f-strings (all ORM-bound; only `text("SELECT 1")` constant); command path is whitelist-only (`CommandType` + `CommandBuilder`, CRLF-tested); SN charset rejects SQL/CRLF/traversal; no shell/subprocess/eval; no `dangerouslySetInnerHTML` (no HTML rendering at all); no secrets in repo (scan clean; only test-code `password=` kwarg matched); `.env`/PEM absent from repo.
- Gaps: **no rate limiting enforced (H-01)**; full-body `await request.body()` precedes the size check, so chunked bodies without `Content-Length` bypass the cheap pre-check (M, folded into H-01 remediation); `X-Forwarded-For` trusted unconditionally for audit IPs (L-04); no CORS (fail-closed — breaks browser frontend until configured, L-04); no in-app security headers (proxy concern, INFO); `/ready` renders exception strings (L-03); `/docs` + ADMS-in-OpenAPI exposed (L-03).

## 10. Frontend Audit — 2/10

`lib/api.ts` (28 lines, no auth lifecycle: no login form, token storage, refresh-on-401, 403/404/422/429/500 handling, retry-guard) + `types/index.ts` + 8 identical stub pages + empty `components/features/hooks/services` dirs. Zero secrets/`NEXT_PUBLIC_*` exposure (good), zero XSS surface (no rendering), but §§56–63 (dashboard metrics, device detail+counters, server-side attendance table+filters+pagination, device-user ops, command UI, users, audit) are unimplemented, with no tests (`tsc`/`build` unverified here). Token delivery is body-bearer, so storage strategy (memory vs localStorage XSS trade-off) is unresolved — M-07.

## 11. Testing Audit — 7/10

Executed: **78 passed, 0 failed; line+branch coverage 91.61% (gate ≥90 met)**; `ruff check` clean; `ruff format --check` clean (80 files); `mypy --strict` clean (63 files). Tests assert real outcomes (row counts, statuses, wire strings `OK`/`OK: N`/`C:…`, rotation-replay 401, RBAC 403, 413, 503, idempotent re-post `OK: 1 → OK: 0`). Fixtures cover §74 (basic/epoch/duplicate/malformed ATTLOG, USERINFO, registry, device-info, cmdresult). Gaps: entire suite (incl. CI, whose postgres service is unused) runs on **SQLite** — `SKIP LOCKED`, `INET`, native UUID/`TIMESTAMPTZ` paths unverified, and SQLite/PG datetime semantics already forced `_ensure_aware`/`_coerce_ts` workarounds (M-06); no concurrency tests (§106 unmet); no frontend tests (§106 unmet); error-path coverage relies on generic handlers (M-04 untested by design).

## 12. Dependency Audit

`pyproject.toml`: unpinned ranges (`fastapi>=0.115`, etc.), no lockfile → non-reproducible builds (LOW/INFO; installed tree matches spec incl. FastAPI 0.141.1). No abandoned/dangerous packages; `python-jose` is maintenance-mode but correct here (INFO). `package.json`: Next 14.2.5/React 18/Tailwind 3.4 — **no `package-lock.json`, so `npm ci` (CI) cannot succeed** (H-04). `python-multipart` present though no form parsing is used (INFO, harmless).

## 13. Docker / Deployment Audit

`docker-compose.yml` separates postgres/redis/backend/frontend with health-gated deps (good). Findings: **H-03** (image `COPY alembic` = env-only dir; `alembic upgrade head` no-ops; plus missing `backend/.env` for `env_file` breaks `compose up` out of the box); frontend image runs `npm run dev` (no production build, LOW); images run as root (LOW); DB/Redis ports published, weak composed default password, no restart policies (LOW, dev-defaults — must be overridden in prod).

## 14. Performance Audit — 6/10

Good: §24 indexes incl. `(device_id, recorded_at DESC)`, `limit ≤500` + offset on list endpoints, ADMS ingest avoids Celery (replies fast), no N+1 in admin reads. Gaps (M-05): ATTLOG costs ~3 round-trips/line (`_resolve_user_id` + `_already_stored` + INSERT) plus an **O(lines × records)** raw-line remap (`router.py:187-190`) — a 10 MB batch risks device timeouts; RSA PEMs re-read from disk on every token issue/verify (`config.py:51-63`); unbounded `offset`; `attempt_count` grows without max-attempt/expiry policy (`expires_at` never set → `expired` unreachable, L-02).

## 15. Documentation Audit

`ARCHITECTURE.md` + 5 docs are thorough and mostly truthful (§2.1 table honestly says "diseñado"). Contradictions found: TESTING claims PG-backed integration ("PostgreSQL servicio CI") but everything runs SQLite (M-06); §65 claims ADMS excluded from OpenAPI but all `/iclock/*` routes are in-schema with duplicate operation IDs (L-03); §5 tree shows `backend/alembic/` while versions live at root `alembic/versions/` (L-05); `services/command.py` docstring claims row-locked ID allocation that doesn't exist (M-08). Implemented-but-undocumented: memory revocation fallback, `remember_refresh` no-op semantics, `summary`/`disable` endpoints detail. No fake-device contamination anywhere (good).

## 16. Requirements Matrix (condensed; full §0–§108 trace)

| Req | Implemented | Tested | Secure | Evidence | Sev |
|---|---|---|---|---|---|
| §26 5 ADMS endpoints + wire texts | Yes | Yes (7 flows) | Yes | `adms/router.py`, `test_adms_*` | — |
| §27 no JWT on ADMS / §28 SN validation | Yes | Yes | Yes | `validators.py`, 400 tests | — |
| §29 registry idempotent | Yes | Yes | Yes | `router.py:248-292` | — |
| §30–35 cdata/ATTLOG/USERINFO/info/registry parsers | Yes | Yes 91%+ | Yes | `parser.py`, unit tests | — |
| §32 malformed never aborts batch | Yes | Yes | Yes | `test_cdata_attlog_malformed_partial` | — |
| §15 device Password= handling | Partial (raw_body keeps it) | No | Partial | `router.py:91`, `device_user.py` | LOW |
| §36–41 command whitelist + formats | Yes | Yes | Yes | `commands.py`, no shell found | — |
| §42 SHELL disabled | Yes | Yes (422 test) | Yes | grep clean | — |
| §43 SKIP LOCKED drain | Yes (PG) | **No (SQLite skips lock)** | Yes | `command.py:111-112` | MED |
| §44 confirm (0→confirmed) | Yes | Yes | Yes | `command.py:133-165` | — |
| §45–46 derived status, no eviction | Yes | Yes | Yes | `device.py:102-114` | — |
| §47 per-device timezone | Column only, **no setter** | Partial | n/a | grep api/timezone | MED |
| §48–49 JWT RS256/claims/keys | Yes | Yes (incl. confusion) | Yes | `security.py` | — |
| §50 Argon2id | Yes | Yes | Yes | `security.py:20` | — |
| §51 refresh rotation/revocation/logout | Partial (access survives logout; mem fallback) | Yes | Partial | `auth.py`, `revocation.py` | MED |
| §52 rate limiting | **No (config string only)** | No | No | grep 1 match | HIGH |
| §53–55 limits (10 MB/1000/100) | Yes | Yes (413/503/queue) | Partial (chunked pre-check bypass) | router + tests | MED* |
| §§56–62 frontend | Scaffold only | No | n/a | stub pages, empty dirs | MED |
| §63 audit actions | Partial (no user mgmt/device.create/update paths) | Partial | Yes | `audit.py`, tests | LOW |
| §64 versioning `/api/v1` + `/iclock` | Yes | Yes | Yes | `main.py:82-83` | — |
| §65 OpenAPI admin-only | **No (ADMS in schema)** | — | n/a | probe output | LOW |
| §66 envelopes / ADMS plain text | Yes (AppError envelope; `request_id` empty — LOW) | Partial | Yes | `main.py:38-51` | LOW |
| §17 raw payload preserved | Yes | Yes | Partial (L-04 note) | `adms_payloads`, tests | — |
| §18 idempotency | Yes (check + constraint) | Yes (re-post) | Yes | probe `OK:1→OK:0` | — |
| §68 transactions/batch | Yes (savepoints) | Yes | Yes | `attendance.py:133-141` | — |
| §70 Redis roles / §71 Celery-minimal | Yes / stub task | Partial | Yes | `revocation.py`, `maintenance.py` | LOW |
| §§72–74 coverage>90% + fixtures | 91.61%, 78 tests, 8 fixtures | — | n/a | run output | — |
| §76 SpeedFace-V5LP compat | Code-compatible | **No device** | n/a | NOT VERIFIED | INFO |
| §80–81 whitelist/CRLF | Yes | Yes | Yes | `commands.py:26-28`, tests | — |
| §82–83 request_id/structlog/sanitize | Partial (`request_id` empty in error envelope) | Partial | Yes | `main.py:43`, `logging.py:12` | LOW |
| §84 /health /ready | Yes | Yes | Partial (error strings) | `main.py:53-80` | LOW |
| §85 compose / §86 alembic | Compose ok / **migration no-op (H-03)** | No PG run | n/a | Dockerfile, layout | HIGH |
| §88–89 retention/disabled | Yes | Yes | Yes | no delete endpoints | — |
| §91 per-endpoint RBAC | Yes | Yes (403) | Yes | `deps.py` | — |
| §93–94 CI gates | **Broken (H-04)** | — | n/a | ci.yml, no lockfile | HIGH |
| §96–106 phases/roles | F0–F6 done; F3 device pending; F8–F9 this report | — | n/a | — | — |
| User provisioning (implied §9/§102) | **Missing** | — | — | H-02 | HIGH |

\* §53 limit enforced for sized bodies; streaming/chunked hardening outstanding.

## 17. Findings

### H-01 — Rate limiting configured but never enforced — HIGH — Security
- **File:** `backend/app/core/config.py:45` (only occurrence of `rate_limit*` in repo); `backend/app/api/v1/auth.py:22-54`; `backend/app/adms/router.py` (all handlers).
- **Finding:** `rate_limit_login = "10/minute"` is a dead setting. No middleware/dependency (slowapi, Redis counters, nothing) protects `/auth/login`, `/auth/refresh`, command endpoints, or ADMS. Unlimited credential-stuffing and device/request flooding.
- **Why it matters:** §52 is explicit; brute force is the top threat against password auth.
- **Expected:** enforced limits + 429s, per §52 (incl. ADMS storm/serial-enumeration guards).
- **Actual:** unlimited.
- **Recommendation (P0):** Redis-backed fixed-window limiter as FastAPI dependency on login/refresh + ADMS per-SN throttle; 429 tests; document proxy-level limits.

### H-02 — No admin-user provisioning path; `users.write/delete` dead — HIGH — Auth/RBAC
- **File:** `backend/app/api/v1/*` (no POST/PATCH/DELETE users), `backend/app/seed.py` (roles+permissions only), `backend/app/core/constants.py:82-83`.
- **Finding:** no endpoint, CLI, or seed creates `users`. First admin requires hand-inserted rows with hand-made Argon2 hashes — unaudited, error-prone, and it bypasses `audit_logs`. RBAC roles exist but cannot be assigned to anyone operably.
- **Expected:** bootstrapped superuser (env/CLI, §102 users+RBAC operable).
- **Actual:** inoperable without raw DB access.
- **Recommendation (P0):** `createsuperuser` CLI (env password or interactive, Argon2id, audited) + minimal users CRUD guarded by `users.*`; tests for provision/login/disable flows.

### H-03 — Alembic migration tree not shipped → `upgrade head` is a silent no-op — HIGH — Deploy/Data
- **File:** `alembic/versions/0001_initial.py` (root) vs `backend/alembic/` (`env.py` only); `backend/Dockerfile:10`; `backend/pyproject.toml` (`script_location="alembic"`); `docker-compose.yml:41`; `backend/alembic.ini`.
- **Finding:** configured script location resolves to `backend/alembic/` (locally and in the image), which contains no `versions/`. The real migration at root is never copied into the image and never on the resolved path. Fresh `alembic upgrade head` exits 0 doing nothing → backend boots against an empty DB (every request fails). `backend/.env` (compose `env_file`) is also absent, so `compose up` fails before that.
- **Expected:** §86/§107 — migrations runnable from scratch in image and checkout.
- **Actual:** schema creation impossible via documented path.
- **Recommendation (P0):** consolidate to `backend/alembic/versions/`, fix Dockerfile COPY, add CI step running `alembic upgrade head` against PG service + `alembic check`; document `.env`/key bootstrap.

### H-04 — CI quality gates misconfigured — HIGH — Process
- **File:** `.github/workflows/ci.yml`; repo root (no mypy config); `frontend/` (no `package-lock.json`).
- **Finding:** (a) `mypy backend/app` runs from root where no `[tool.mypy]` exists → default (non-strict) settings; the claimed strict gate is enforced only when run from `backend/`. (b) `npm ci --prefix frontend` requires a lockfile that doesn't exist → frontend job always fails.
- **Expected:** §93 gates enforced as specified.
- **Actual:** typing gate fail-open; frontend gate fail-closed-broken.
- **Recommendation (P0):** run backend checks with `working-directory: backend` (or `MYPYPATH`/explicit `--config-file backend/pyproject.toml` + `--strict` parity check), commit `package-lock.json`, and add the PG-backed `alembic upgrade head` step (H-03).

### M-01 — Logout leaves access tokens valid; revocation degrades silently without shared Redis — MEDIUM — Auth
- **File:** `backend/app/api/v1/auth.py:71-84`; `backend/app/core/revocation.py:19-44`.
- **Finding:** logout revokes only the refresh `jti`; the access token stays valid until expiry (15 min window). When Redis is unreachable, revoke/check fall back to process-local memory — across workers/hosts revocation silently stops working.
- **Expected:** §51 logout = session termination; revocation effective wherever tokens are verified.
- **Actual:** partial logout; topology-dependent revocation.
- **Recommendation (P1):** short-lived access blacklist (or logout revokes presented access `jti` too), Redis-required readiness for auth writes, alerting on fallback, multi-worker test.

### M-02 — Device timezone not manageable — MEDIUM — Protocol/Data
- **File:** `backend/app/models/device.py:43`; `backend/app/api/v1/*` (zero timezone writes per grep).
- **Finding:** §47 requires per-device timezones (e.g. `America/Mexico_City`); the column exists (default UTC) but no admin endpoint sets it, so non-UTC fleets get misinterpreted ATTLOG timestamps.
- **Recommendation (P2):** PATCH device (`timezone`, validated via `ZoneInfo`, audited) + test with non-UTC ATTLOG.

### M-03 — Device-user created locally before device confirmation; no update path — MEDIUM — Design
- **File:** `backend/app/api/v1/resources.py:99-152` vs spec §61 ("never modify the table expecting the device to change").
- **Finding:** POST stages a `DeviceUser` row immediately while the command may never confirm; there is no PUT/edit endpoint although §61/§63 require edit + `device_user.update` audit.
- **Recommendation (P2):** pending-intent model or confirmation-reconciled staging + PUT endpoint; tests for confirm/timeout reconciliation.

### M-04 — ADMS internal failures return 200 OK — MEDIUM — Reliability
- **File:** `backend/app/adms/router.py:157-171,288-291,319-322,371-374`.
- **Finding:** any exception mid-`cdata`/`registry`/`getrequest`/`devicecmd` rolls back and replies `OK`, so a device can discard data the server never stored; detection depends on logs/events that themselves need a working DB.
- **Expected:** fail-safe signal the device will retry on, or documented at-least-once contract.
- **Actual:** silent success.
- **Recommendation (P2):** distinguish retryable (5xx-style device-retryable text) from applied; alert on `adms_error`; chaos test for DB-down behavior.

### M-05 — ATTLOG ingest cost risks device timeouts on large batches — MEDIUM — Performance
- **File:** `backend/app/adms/router.py:187-190` (O(lines×records) remap); `backend/app/services/attendance.py:89-141` (2 SELECT + INSERT per line).
- **Finding:** ~3 round-trips per record plus quadratic remap before responding; legal 10 MB pushes can exceed device patience.
- **Recommendation (P7):** single bulk dedup (`WHERE (pin,recorded_at,…) IN`), per-device user-map cache, attach raw line in `parse_attlog`; soak test with 100k-line payload.

### M-06 — Suite (incl. CI) is SQLite-only; PG paths unverified — MEDIUM — Testing
- **File:** `backend/tests/conftest.py` (hardwired sqlite file), `.github/workflows/ci.yml` (postgres service unused), `services/*` (`_ensure_aware`/`_coerce_ts` workarounds prove semantic drift).
- **Finding:** `FOR UPDATE SKIP LOCKED`, `INET`, native UUID/`TIMESTAMPTZ`, tz-aware comparisons never execute under test; `docs/TESTING.md` claims PG-backed integration.
- **Recommendation (P4):** run integration job against CI postgres (env-switchable `DATABASE_URL`), keep sqlite for unit-only; add concurrent-poll ATTLOG test (§106).

### M-07 — Frontend is scaffold-only; token lifecycle unresolved — MEDIUM — Frontend
- **File:** `frontend/app/*/page.tsx` (identical stubs), `frontend/lib/api.ts` (no storage/refresh/401/429/retry/pagination/RBAC), empty `components/features/hooks/services`.
- **Finding:** §§56–63 unimplemented; body-bearer tokens with no secure-storage strategy; `tsc`/`build`/tests unverifiable here (no Node).
- **Recommendation (P6):** implement per §56–63 with httpOnly-cookie or memory-token decision documented, 401→refresh→retry with loop guard, route guards mirroring backend denials, and `eslint+typecheck+build` green in CI (after H-04).

### M-08 — Protocol command IDs allocated MAX+1 without a lock (docstring claims otherwise); device-limit check races — MEDIUM — Concurrency
- **File:** `backend/app/services/command.py:3-5` vs `:78-82`; `backend/app/services/device.py:54-57`.
- **Finding:** concurrent `queue_command` calls can mint duplicate `protocol_command_id` → unique violation (admin 500) or, worse, wire-ID confusion; concurrent registrations can overshoot `max_devices`.
- **Recommendation (P2):** PG advisory lock / `SELECT … FOR UPDATE` on a per-device counter row (or sequence), atomic limit enforcement; concurrency tests.

### LOW findings
- **L-01 API robustness (proven):** duplicate `POST /device-users/{id}` (same pin) → **500 "Internal Server Error"** (reproduced live: `create1: 201 | duplicate-create: 500`) instead of 409; naive `date_from/date_to` may 500 on PG; `pin`/`name` lengths unbounded vs `VARCHAR(64/255)`. Files: `resources.py:99-152,26-38`.
- **L-02 Schema nits:** redundant `ix_attendance_device_recorded_desc` and `ix_cmd_device_proto` (duplicates unique backing index); `DeviceEvent.id` lacks UUID default; `expires_at` never set → `expired` unreachable; `attempt_count` unbounded. Files: `models/device.py:141,166-167,190-199,205`.
- **L-03 API surface hygiene:** `/iclock/*` in OpenAPI with duplicate operation IDs (contradicts §65; probe-verified); `/docs` served unconditionally; `AppError` envelope `request_id` always `""` (`main.py:39-43`); `/ready` renders exception strings (`main.py:69-77`).
- **L-04 Hardening notes:** `X-Forwarded-For` trusted without proxy allowlist (`deps.py:65-68`, audit-IP spoofable); no CORS (fail-closed — browser UI blocked until configured); no in-app security headers (proxy-owned, document); RSA PEMs re-read per token op (`config.py:51-63`, cache them); unknown-user login skips Argon2 (timing oracle, negligible); `adms_payloads.raw_body` retains USERINFO `Password=` values — document acceptance or redact on store; lowercase `table=` is swallowed as device-info (silent loss if a firmware ever deviates); `int("1_0")==10` vs Laravel's `0` (trivial).
- **L-05 Process/docs:** `seed.py` uses `create_all` bypassing Alembic (§86); disable-device is API-irreversible (no re-enable); `inspect`-when-enabled returns `"devices": []`; dead code (`new_request_id`, prod-unused `body_preview`, unexposed cancel/expire, no-op Celery stub — acceptable per §71 but label it); `ARCHITECTURE.md §5` shows `backend/alembic/` while versions ship at root; committed `backend/zkteco_adms.egg-info/` build artifact.
- **L-06** No account lockout/breach throttling (extends H-01; listed for remediation completeness).

### INFO (no action strictly required)
- **I-01 ADMS REAL DEVICE VALIDATION = NOT VERIFIED** (no SpeedFace-V5LP available; code-compatible only — see §66–67).
- **I-02** `python-jose` is maintenance-mode; usage is correct — consider `PyJWT` long-term.
- **I-03** Single-tenant object access (UUID + permission, no row ownership) is a reasonable documented assumption, not an IDOR.
- **I-04** Loose dependency ranges, no backend lockfile — pin/lock for reproducible, scannable builds.
- **I-05** `python-multipart` unused; `DEBUG=false` default good; `.env.example` contains no secrets (good).

## 18. Critical Issues

None found. No arbitrary execution, exposed private keys, exploitable SQLi, auth bypass, mass data-loss path, or shell capability.

## 19. High Issues

H-01 (no rate limiting), H-02 (no user provisioning), H-03 (Alembic no-op deploys), H-04 (CI gates misconfigured). Details in §17.

## 20. Medium Issues

M-01 (logout/revocation gaps), M-02 (timezone unmanageable), M-03 (§61 staging violation + no edit), M-04 (silent 200 on failure), M-05 (ingest cost), M-06 (SQLite-only suite), M-07 (frontend scaffold), M-08 (ID/limit races). Details in §17.

## 21. Low Issues

L-01…L-06 as listed in §17 (proven 500-on-duplicate included).

## 22. Recommended Remediation Plan

- **P0 — Critical security/process (pre-release blockers):** H-01 (Redis limiter + 429s + ADMS throttle + tests); H-02 (createsuperuser CLI + users CRUD + bootstrap docs + tests); H-03 (consolidate `backend/alembic/versions`, Dockerfile COPY, PG `upgrade head` in CI + `alembic check`); H-04 (CI `working-directory: backend` for strict mypy parity, commit lockfile, frontend job green).
- **P1 — High security/data integrity:** M-01 (revoke access `jti` on logout; Redis-required auth path + fallback alerting; multi-worker test).
- **P2 — Protocol compatibility:** M-02 (timezone PATCH + non-UTC test); M-03 (pending-intent/user PUT + reconciliation tests); M-08 (locked ID allocation + concurrency tests); M-04 (retryable-vs-applied ADMS failures + DB-down test).
- **P3 — Database:** L-02 (drop redundant indexes, UUID default for events, expiry/attempt policy); PG-backed verification of migration (§18 on real PG).
- **P4 — Tests:** M-06 (PG integration job, concurrency tests); L-01 regression tests (409 duplicate, aware-date validation, length limits).
- **P5 — Architecture:** remove dead code, fix lock-claim docstring, split `resources.py` per §5, cache RSA keys.
- **P6 — Frontend:** M-07 full scope §§56–63 + storage decision + guards + tests; L-07 prod image (`next build/standalone`).
- **P7 — Performance:** M-05 bulk ingest + soak test; offset caps/keyset pagination for `attendance`.
- **P8 — Documentation:** fix TESTING (SQLite reality), §65 (OpenAPI), alembic tree, `Password=` retention acceptance; record single-tenant assumption and proxy responsibilities (TLS/HSTS/CSP/rate limits/CORS).

## 23. Final Verdict

**FAIL** — 0 CRITICAL, **4 HIGH**, 8 MEDIUM, 6 LOW-group findings. Backend core (parsers, whitelist, JWT, RBAC, idempotency) is solid and well-tested, but release is blocked by unenforced rate limiting, inoperable user provisioning, a no-op migration chain, and misconfigured CI gates — plus an entirely stub frontend and no real-device validation.

### Scores

```text
Architecture:   8/10
ADMS:           8/10
Database:       8/10
Security:       6/10
Authentication: 6/10
Authorization:  7/10
Testing:        7/10
Frontend:       2/10
Performance:    6/10
Documentation:  8/10
Overall Score:  66/100
```

### Execution evidence (this audit, read-only runs)

```text
pytest tests --cov=app --cov-report=term-missing --cov-fail-under=90 → 78 passed, 91.61% (gate met)
ruff check app tests alembic → All checks passed
ruff format --check app tests alembic → 80 files already formatted
mypy app (backend/, strict) → Success, 63 files
probe: duplicate device-user create → 201 then 500 "Internal Server Error" (L-01 proven)
probe: /openapi.json contains /iclock/* with duplicate operation IDs (L-03/§65 proven)
NOT run here (no servers): alembic upgrade head vs PG, npm typecheck/build, device traffic
```

### Acceptance (§100–101, §66–67)

```text
ADMS REAL DEVICE VALIDATION = NOT VERIFIED (no SpeedFace-V5LP available)
Registry→FastAPI→PostgreSQL→attendance→Next.js chain = UNVERIFIED end-to-end
CODE COMPATIBILITY (vs Laravel reference) = PASS
```
