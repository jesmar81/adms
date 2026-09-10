# TESTING

Cobertura objetivo **>90%** (línea+rama, gate `--cov-fail-under=90`) — estado
2026-09-10: **148 tests, 93%**. Prioridad: parsers ADMS, ATTLOG, USERINFO,
registry, command results, cola, idempotencia, registro, online/offline,
JWT, Argon2id, RBAC, rate limiting, provisioning, lifecycle, concurrencia.

## 1. Estrategia de backends (M-06)

- **Unit + integración base: SQLite** (rápido, hermético). Cubre lógica,
  parsers, API, RBAC, idempotencia y todos los flujos ADMS.
- **Integración PG: PostgreSQL real** cuando `ZKTECO_TEST_PG_URL` está
  definido (job `backend-postgres` de CI, obligatorio). Sin la variable, los
  tests `pytest.mark.pg` hacen skip explícito — nunca fingen pasar en PG.
  El esquema PG se construye con `alembic upgrade head` (nunca `create_all`),
  de modo que estos tests también prueban la cadena de migración.
- **Redis en tests:** fakeredis hermético por defecto
  (`ZKTECO_USE_REAL_REDIS=1` en CI para el servicio real).
- Divergencias conocidas SQLite/PG (`_ensure_aware`, `_coerce_ts`) aisladas en
  `services/attendance.py` y `services/device.py`, cubiertas en ambos backends.

## 2. Layout real

```text
backend/tests/
├── unit/                  # puros (+ repos/servicios con sqlite)
│   ├── test_parser_attlog.py
│   ├── test_parser_misc.py      # USERINFO/KV/registry/cmdresult
│   ├── test_protocol_core.py    # builders, wire, online/offline
│   ├── test_security_crypto.py  # Argon2id + JWT RS256 + confusion
│   ├── test_coverage_extra.py
│   └── test_gaps.py
├── integration/
│   ├── test_adms_registry_cdata.py
│   ├── test_adms_commands.py    # + concurrencia lógica
│   ├── test_auth.py             # login/refresh/logout/revocación/RBAC
│   ├── test_admin_api.py
│   ├── test_users.py            # provisioning + guards + CLI
│   ├── test_ratelimit.py        # 429/lockout/fail-closed/fail-open/shared
│   ├── test_lifecycle.py        # M-02/M-03/M-04/M-08/L-01/L-02 + soak 20k
│   ├── test_hardening.py        # L-03/L-04
│   ├── test_coverage2.py
│   ├── test_gaps.py
│   └── test_postgres.py         # [pg] tipos/constraints/índices/flujo/
│                                # concurrencia real SKIP LOCKED/bulk/seed
└── fixtures/              # registry, ATTLOG(+epoch/dup/malformed),
                           # USERINFO, device-info, cmdresult (§74)
```

## 3. Comandos

```bash
cd backend
pytest -q                                                        # todo (sqlite)
ZKTECO_TEST_PG_URL="postgresql+asyncpg://u@/db?host=..&port=.." \
  pytest -q                                                      # + PG (M-06)
pytest -q tests/unit                                             # parsers, sin infra
pytest --cov=app --cov-report=term-missing --cov-fail-under=90
ruff check app tests alembic && ruff format --check app tests alembic
mypy --strict app                                                 # estricto explícito (H-04)
alembic upgrade head && alembic check                             # necesita PG (H-03)
```

Frontend (`frontend/`, requiere Node 20):

```bash
npm ci && npm run lint && npm run typecheck && npm run build
```

## 4. Reglas

- Parsers: tabla de casos (válido/malformado/epoch/edge). Ningún `NULL`/
  timestamp inventado (§32). `raw_line` se preserva en el parse (M-05).
- Integración ADMS (§73): los 7 flujos con respuestas wire exactas (`OK`,
  `OK: N`, `C:…`, `ERROR`+500 en fallo de persistencia).
- Idempotencia: reenviar el mismo ATTLOG → sin duplicados (sqlite y PG);
  confirms repetidos → un solo evento.
- Concurrencia (PG): polls simultáneos → comandos distintos; 20 queues
  concurrentes → IDs 1..20 únicos; límite de dispositivos exacto.
- Seguridad: JWT confusion, replay tras logout total, RBAC 403, SHELL
  rechazado, CRLF rechazado, oversized 413, 429 con `Retry-After`,
  lockout, fail-closed sin Redis, redacción `Password=`, 422 sin paths.
- Soak: 20k líneas ATTLOG en una petición (límite 60 s; medido ~6 s sqlite,
  5k PG ~3 s).
- Prohibido: tests que solo afirman status sin validar estado; marcar FIXED
  sin test que lo demuestre.
