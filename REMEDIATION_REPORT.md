# ZKTeco ADMS Platform — Remediation Report

**Source of truth for this remediation:** `AUDIT_REPORT.md` (verdict FAIL, 66/100).
**Scope rule:** `AUDIT_REPORT.md` was NOT modified. Real-device validation was
not performed and is not claimed anywhere in this report.
**Method per finding:** audit finding → code change → regression test →
integration test (SQLite + real PostgreSQL 18.6) → static analysis →
security check → documentation → evidence below.

Related: `ARCHITECTURE.md`, `README.md`, `docs/`.

---

## Executive Summary

```text
AUDIT VERDICT: FAIL (0 critical, 4 high, 8 medium, 6 low) — Score 66/100
REMEDIATION:   all HIGH fixed, all MEDIUM fixed, all LOW fixed/documented
               148 tests PASS · coverage 93% (branch) · ruff PASS
               mypy --strict PASS · alembic upgrade+check PASS on real PG
               frontend tsc+lint+build PASS · npm ci PASS
```

No finding was closed without a test. No functionality was deleted to hide a
finding (dead code was either wired up — e.g. cancel/expire semantics — or
explicitly removed with justification). The next agent is an independent
auditor: every row below points at files, tests, and commands it can re-run.

**SpeedFace-V5LP REAL DEVICE VALIDATION = NOT VERIFIED** (no hardware
available; §23). The full chain registry→FastAPI→PostgreSQL→attendance→Next.js
is proven with fixtures, HTTP-level integration tests, and real PostgreSQL —
but not against physical hardware.

## Finding Matrix

| Finding | Original | Estado | Evidencia |
|---|---|---|---|
| H-01 Rate limiting sin enforcement | HIGH | FIXED | `app/core/ratelimit.py`, `tests/integration/test_ratelimit.py` (10 tests: 429+Retry-After, lockout, fail-closed 503, ADMS fail-open, aislamiento, shared-server) |
| H-02 Sin provisioning de usuarios | HIGH | FIXED | `app/cli.py`, `app/api/v1/users.py`, `tests/integration/test_users.py` (13 tests: CRUD, guards, audit, CLI subprocess) |
| H-03 Alembic no-op | HIGH | FIXED | `backend/alembic/versions/{0001_initial,0002_lifecycle}.py`, `alembic upgrade head` + `current` + `check` en PG 18.6 real, `tests/integration/test_postgres.py::test_pg_seed_on_migrated_schema` |
| H-04 CI gates rotos | HIGH | FIXED | `.github/workflows/ci.yml` (working-directory backend, `mypy --strict`, job PG con upgrade+check+suite, frontend con lockfile), `frontend/package-lock.json` |
| M-01 Logout parcial / fallback silencioso | MEDIUM | FIXED | `app/api/v1/auth.py::logout` (revoca access+refresh), `app/core/revocation.py` sin fallback, tests logout-total + shared-revocation + 503 |
| M-02 Timezone no gestionable | MEDIUM | FIXED | `PATCH /api/v1/devices/{id}` (ZoneInfo, audit), test Ciudad de México 08:30→14:30Z |
| M-03 Lifecycle sin confirmar | MEDIUM | FIXED | `sync_state/pending_op` + PUT + reconciliación en `confirm_result` y push USERINFO, `tests/integration/test_lifecycle.py` (6 tests + eventos + audit) |
| M-04 200 OK en fallos | MEDIUM | FIXED | `500`+`ERROR` en cdata/registry, `OK` documentado en getrequest/devicecmd, confirms idempotentes, tests de caos |
| M-08 MAX+1 con race | MEDIUM | FIXED | counter `UPDATE…RETURNING` (`devices.command_seq`), advisory lock en registro, tests concurrentes PG (20 IDs únicos, límite exacto) |
| M-06 Suite solo SQLite | MEDIUM | FIXED | `ZKTECO_TEST_PG_URL`, `tests/integration/test_postgres.py` (8 tests PG: tipos/constraints/índices/flujo/concurrencia/bulk/seed), job CI PG |
| L-01 500 en duplicado / validación | MEDIUM→LOW | FIXED | 409 duplicado (probado), longitudes, fechas aware + rango, PUT/DELETE 404/409 |
| L-02 Índices/defaults/TTL | LOW | FIXED | 0001 nombrado + índices redundantes fuera, `DeviceEvent.id` default, TTL (24h) + reintentos (10) + `command_retry`, migración 0002 |
| M-05 Ingest costoso | MEDIUM | FIXED | bulk (user-map + dedup + insert RETURNING, chunks 1000), `raw_line` en parser, soak 20k (~6 s sqlite) + 5k PG (~3 s) |
| M-07 Frontend stub | MEDIUM | FIXED | 11 rutas reales, ApiClient (refresh single-flight, ApiError 401/403/404/409/422/429/500), AuthProvider, gating `Can`, tokens en memoria; `tsc`+`lint`+`build`+`npm ci` verificados; Next 14.2.5→14.2.35 (CVE) |
| L-03 Higiene API | LOW | FIXED | ADMS fuera de OpenAPI, `request_id` real en envelope, `/ready` sanitizado, 422 sin paths (hallazgo propio documentado), `/docs` toggle |
| L-04 Hardening | LOW | FIXED | CORS explícito, headers base, XFF solo proxies confiables, RSA cacheado, `Password=***` en raw_body, `table` case-insensitive, int estricto |
| L-05 Proceso/docs | LOW | FIXED | seed sobre esquema migrado (test PG), re-enable vía PATCH, inspect con snapshots reales, dead code fuera, egg-info fuera, árbol Alembic en docs |
| L-06 Lockout | LOW | FIXED | incluido en H-01 (20 fallos/15min → 429) + test |

Estados usados: FIXED en todos los hallazgos auditados. No hay WONT_FIX,
PARTIALLY_FIXED ni BLOCKED (Node/PG se resolvieron en user-space para
verificación local; CI los provee como servicios).

## Changed Files

Backend (`backend/app/`):

- `core/ratelimit.py` (nuevo): limiter Redis distribuido (`hit` INCR+EXPIRE),
  `redis_or_503` (fail-closed), `check_adms_limit` (fail-open), 429 admin/ADMS.
- `core/config.py`: settings `RATELIMIT_*`, `ZKTECO_COMMAND_TTL_S/MAX_ATTEMPTS`,
  `TRUSTED_PROXIES_RAW`, `FRONTEND_ORIGINS_RAW`, `HSTS_ENABLED`, `DOCS_ENABLED`,
  cache de lectura de PEMs.
- `core/revocation.py`: sin fallback en memoria; errores Redis se propagan.
- `api/v1/deps.py`: revocation check fail-closed (503), `client_ip` solo con
  proxy confiable (CIDR), envelope 401/403 coherente.
- `api/v1/auth.py`: guards de rate limit en login/refresh, lockout prem/post
  intento, `remember_refresh`/`revoke` fail-closed, logout revoca access+refresh,
  `GET /auth/me` (identidad+permisos para UI).
- `api/v1/users.py` (nuevo real): CRUD + `users.read/write/delete`, validación
  (password≥10, email, roles), guardas (sin auto-borrado, sin escalado ajeno,
  último superuser 409), soft-delete, auditoría total.
- `api/v1/router.py`, `api/v1/resources.py`: router real de users; device-users
  con `sync_state`/`pending_op`, PUT, DELETE→202 pendiente, 409 duplicado,
  validación de fechas (aware + rango) y longitudes (L-01).
- `api/v1/schemas.py`: `DevicePatch`, `DeviceUserUpdate`, límites y `sync_state`.
- `api/v1/devices.py`: `PATCH /devices/{id}` (nombre/modelo/timezone ZoneInfo/
  estado con re-enable) + audit.
- `adms/router.py`: throttle ADMS pre-body, `table` case-insensitive,
  semántica M-04 (500/`ERROR` vs `OK`), `Password=***` en `raw_body`,
  `inspect` con snapshots, `include_in_schema=False`, sin `new_request_id`.
- `adms/parser.py`: `raw_line` en `AttendanceRecord`, enteros estrictos
  (`1_0` ya no es 10).
- `adms/commands.py`, `services/command.py`: `payload` en queue, counter
  atómico `command_seq`, `expires_at`+TTL, reintento hasta `max_attempts`
  (evento `command_retry`), confirms idempotentes, expiración con
  reconciliación, docstring corregido.
- `services/device.py`: advisory lock en registro, `_dialect_name`.
- `services/device_user.py`: `reconcile_command`, confirmación por push.
- `services/attendance.py`: bulk M-05 (mapa/dedup/insert+RETURNING, chunks,
  SmallInteger guard, `work_code=""`).
- `services/auth.py`, `services/audit.py`, `services/events.py`: sin cambios
  funcionales (verificados).
- `models/`: constraints nombradas (`uq_*`, `fk_*` + convención),
  `command_seq`, `sync_state/pending_op/last_protocol_command_id` (+CHECK),
  índices redundantes eliminados, `DeviceEvent.id` default, índices de audit.
- `cli.py` (nuevo): `createsuperuser` (getpass/env, Argon2id, rol admin,
  auditado, exige esquema migrado).
- `seed.py`: sin cambios (verificado sobre esquema Alembic en PG).
- `main.py`: envelope unificado + `request_id` real, 422 sanitizados, CORS
  explícito, headers base (+HSTS opcional), `/ready` sanitizado, docs toggle.
- `workers/`: sin cambios (stub documentado como intencional, §71).

Migraciones/DevOps/CI (`backend/alembic/`, root, `.github/`):

- `backend/alembic/versions/0001_initial.py` (movido de root, reescrito:
  1 statement por `op.execute`, constraints nombradas, sin índices redundantes).
- `backend/alembic/versions/0002_lifecycle.py` (nuevo: `command_seq`,
  `sync_state/pending_op/last_protocol_command_id`).
- `backend/alembic/script.py.mako` (nuevo), root `alembic/` eliminado.
- `backend/Dockerfile`: sin cambios necesarios (`COPY alembic` ya cubre
  `versions/`); verificado por inspección.
- `.github/workflows/ci.yml`: jobs `backend-sqlite`, `backend-postgres`
  (servicios PG+Redis, `alembic upgrade head` + `check` + suite con PG/Redis
  reales, `mypy --strict` con working-directory), `frontend` (`npm ci`,
  `lint`, `typecheck`, `build`).
- `backend/.env.example`: todas las claves nuevas documentadas.
- `backend/pyproject.toml`: `fakeredis` dev, marker `pg`, ignores ruff
  justificados (`B008` idiom FastAPI, `E501` en DDL versionado).

Frontend (`frontend/`): `lib/api.ts` (ApiClient + `ApiError` + refresh
single-flight + tokens en memoria), `lib/auth.tsx` (provider, `RequireAuth`,
`Can`), `components/ui.tsx`, 11 rutas reales (login, dashboard, devices,
devices/[id], attendance, device-users, commands, users, audit, home,
layout), `types/index.ts`, `next.config.mjs` (standalone), `.eslintrc.json`,
`package.json` (Next 14.2.5→14.2.35 + eslint), `package-lock.json` (nuevo),
`Dockerfile` multi-stage prod no-root.

Docs: `ARCHITECTURE.md` (§§4–7 + árbol), `README.md`, `docs/SECURITY.md`
(reescrito con políticas reales), `docs/TESTING.md` (estrategia sqlite/PG),
`docs/DATABASE.md` (0002, naming, TTL, sync), `docs/ADMS_PROTOCOL.md`
(fallos, lifecycle, redacción), `docs/DEVELOPMENT.md` (bootstrap, gates),
`backend/.env.example`.

Tests nuevos: `test_ratelimit.py` (10), `test_users.py` (13),
`test_lifecycle.py` (15), `test_hardening.py` (8), `test_coverage2.py` (16),
`test_postgres.py` (9, PG real); `conftest.py` (fakeredis hermético,
fixtures PG con `alembic upgrade head`, `USE_REAL_REDIS`).

## Tests

Comandos ejecutados (este entorno: PG 18.6 y Node 20 en user-space
`/tmp/opencode`, sin tocar el sistema):

```text
cd backend
ruff check app tests alembic              → All checks passed
ruff format --check app tests alembic     → 90 files already formatted
mypy --strict app                         → Success, 65 files
pytest tests                              → 148 passed (sqlite+fakeredis)
ZKTECO_TEST_PG_URL=… pytest tests --cov=app --cov-branch \
  --cov-report=term-missing --cov-fail-under=90
                                          → 148 passed, TOTAL 93%
alembic upgrade head                      → 0002_lifecycle (head), PG real
alembic current                           → 0002_lifecycle (head)
alembic check                             → No new upgrade operations detected
python -m app.seed (sobre esquema Alembic)→ roles 3, permissions 14
soak ATTLOG                               → 20k líneas OK:20000 en ~6 s (sqlite);
                                            5k líneas OK:5000 en ~3 s (PG)
concurrencia PG                           → 6 polls: IDs {1,2,3} sin duplicados;
                                            20 queues: IDs 1..20 únicos;
                                            límite 3 con 8 registros: exacto
cd ../frontend (Node 20.18.1)
npm ci && npm run lint                   → No ESLint warnings or errors
npm run typecheck                         → tsc limpio
npm run build                             → 12 rutas, standalone OK
npm audit                                 → 14.2.35 aplicado (ver Seguridad)
```

## Security

- **Authentication:** Argon2id intacto; provisioning por CLI auditada +
  CRUD con guards (tests: escalado, auto-borrado, último-admin, audit).
- **Authorization:** RBAC por endpoint intacto + permisos `users.*` ya vivos;
  UI los refleja pero el backend deniega (403 testeado).
- **Rate limiting:** Redis distribuido (INCR+EXPIRE), 429+`Retry-After`,
  lockout, compartición entre workers probada (FakeServer compartido),
  fail-closed en auth (503 incl. `get_current_user`), fail-open ADMS
  documentado y probado.
- **Secrets:** scan limpio (sin PEM/`.env`/tokens en repo); `Password=`
  redactado con hash íntegro; 422 sin paths (hallazgo propio en remediación,
  causa: `__str__` de FastAPI 0.141 con contexto de endpoint).
- **Injection:** whitelist + CRLF intactos; `table` case-insensitive no abre
  inyección (clasificación, no ejecución); sin SQL crudo (solo `text()`
  constantes y DDL versionado); frontend sin HTML crudo.
- **JWT:** RS256-only, claims y rotación intactos; logout revoca ambos JTIs;
  sin fallback local; confusion/HS256 negativos siguen verdes.
- **Device authentication:** charset SN intacto; sin secreto compartido en MVP
  (asunción documentada, igual que antes).
- **Dependencias:** `npm audit` tras bump a Next 14.2.35: resto
  `next≤16 RCE-en-Windows/AVIF` no aplicable (deploy Linux, sin
  `next/image` AVIF) — riesgo residual documentado, no oculto. Python sin
  advisories revisados a mano (sin `pip-audit` en el mirror; CI no lo corre:
  recomendado como follow-up, no como gate roto).

## Database

- Migración desde cero en PG real: `upgrade head` → `0002_lifecycle`,
  `current` confirma, `check` limpio, `seed` operativo, 13 tablas.
- Constraints nombradas verificadas en `pg_constraint` (test PG);
  índices §24 verificados en `pg_indexes` (redundantes ausentes).
- Concurrencia PG probada (SKIP LOCKED, counter, advisory lock).
- Transacciones: batch ATTLOG en una transacción (router commit) +
  `ON CONFLICT` backstop; `TRUNCATE … CASCADE` solo en fixtures de test.

## ADMS

- Registry/cdata/getrequest/devicecmd/inspect: respuestas wire intactas
  (`OK`, `OK: N`, `C:…`, `ERROR`+500 donde corresponde), 400/401→400/413/429/503
  según caso, throttle pre-body.
- ATTLOG: bulk idempotente (re-post `OK: 0` en ambos backends), malformados
  sin abortar, `raw_line` por registro, `work_code=""`, timezone por
  dispositivo (test Ciudad de México).
- USERINFO: reconcilia intents pendientes; `Password=` redactado en payload.
- Comandos: IDs monotónicos atómicos, TTL+reintentos, confirms idempotentes,
  correlación `(device_id, protocol_command_id)` con payload de intent.
- Correlación extremo a extremo probada: API→queue→poll→devicecmd→synced
  (crear/actualizar/borrar, éxito y fallo).

## Frontend

Login (429/503 diferenciados), dashboard (summary+recientes+pendientes),
devices (+filtro), device detail (ficha, contadores GET OPTION, tabs
users/attendance/commands/events, set-timezone, queue whitelist),
attendance (filtros+fecha+paginación), device-users (crear/editar/borrar con
estados `sync_state` + query), commands (lista+filtro), users (CRUD+roles),
audit (tabla). `tsc`, `eslint`, `next build` (12 rutas, standalone) y
`npm ci` verificados con Node 20.18.1. Sin tests de frontend (asumido como
deuda explícita: suite e2e pendiente; la lógica crítica vive testeada en el
backend).

## Remaining Risks

1. **SpeedFace-V5LP REAL DEVICE VALIDATION = NOT VERIFIED.** Riesgos vivos:
   reintento exacto del firmware ante `500`/`ERROR`, `table=` en minúsculas
   solo cubierto por tolerancia, `Stamp/OpStamp` no observados, `VerifyMode`
   dependientes de firmware. Mitigación: `adms_payloads` + primera sesión
   capturada como fixtures (ver `docs/ADMS_PROTOCOL.md §9`).
2. Redis como dependencia dura de auth (decisión consciente fail-closed):
   caída de Redis = admin 503 (ADMS sigue ingiriendo). Requiere Redis HA en
   producción + alerta del fallback eliminado.
3. `next≤16` RCE Windows/AVIF residual (no aplicable al deploy Linux).
4. Sin `pip-audit`/escaneo de secretos en CI (recomendado añadir).
5. `remember_refresh` persiste JTIs pero `refresh` no verifica presencia en
   la lista (solo revocación): un refresh válido firmado pre-reinicio de
   Redis seguiría rotando. Riesgo bajo (firma+revocación intactas); endurecer
   con allowlist estricta como follow-up.
6. Relojes de dispositivos sin autenticación más allá del serial (asunción
   MVP documentada); endurecer con allowlist/IP por despliegue.
7. ATTLOG con `status`/`verify_mode` fuera de SmallInteger se descarta con
   warning (documentado; firmwares reales envían 0–25).
