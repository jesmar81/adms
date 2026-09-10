# ARCHITECTURE — ZKTECO ADMS PLATFORM (Python)

> **Única fuente de verdad arquitectónica del proyecto.**
> Los documentos en `docs/` son especificaciones técnicas subordinadas.
> Ante cualquier contradicción, prevalece este archivo.

- Stack: Python 3.12+ · FastAPI 0.141.1 · PostgreSQL + asyncpg · SQLAlchemy 2.x async ·
  Alembic · Redis · Celery (solo reportes/exports/mantenimiento) ·
  Next.js + TypeScript + Tailwind · JWT RS256 · Argon2id · Docker Compose ·
  Pytest · Ruff · Mypy.
- Dispositivo objetivo: **ZKTeco SpeedFace-V5LP** vía **ADMS over HTTP**.
  No se implementa TCP/UDP 4370 ni SDK DLL en el MVP (§76–78).
- Prioridad absoluta: un SpeedFace-V5LP real debe poder
  registrarse → aparecer en `devices` → actualizar `last_activity_at` →
  enviar ATTLOG → persistir `attendance_logs` (§100, §107).

---

## 1. Topología

```text
                    ┌────────────────────────┐
                    │     SpeedFace-V5LP     │
                    └────────────┬───────────┘
                                 │ ADMS HTTP (sin JWT)
                                 ▼
                    ┌────────────────────────┐
                    │    FastAPI ADMS        │
                    │       Gateway          │
                    │  /iclock/*  (texto)    │
                    └────────────┬───────────┘
                                 │
                 ┌───────────────┼────────────────┐
                 │               │                │
                 ▼               ▼                ▼
            PostgreSQL         Redis           Workers (Celery)
          (source of truth) (revocación/     (reportes, exports,
                             rate-limit/      cleanup, analytics)
                             locks/caché)
                 │
                 ▼
          Administrative API (/api/v1/*, JWT RS256 + RBAC)
                 │
                 ▼
              Next.js
```

Dos superficies separadas (§4, §64):

| Superficie | Prefijo | Auth | Formato |
|---|---|---|---|
| ADMS (dispositivos) | `/iclock/*` | validación de `SN`, sin JWT (§27) | `text/plain` wire protocol, jamás JSON arbitrario (§66) |
| API administrativa | `/api/v1/*` | JWT RS256 access+refresh + permiso por endpoint (§91) | JSON + envelope de error `{"error": {code,message,request_id}}` (§66) |
| Salud | `/health`, `/ready` | ninguna | JSON |

---

## 2. Reverse engineering del repositorio Laravel (FASE 0)

Referencia: `athwari/laravel-zkteco-adms-server` — estudiada como **referencia
funcional del protocolo**, no para port mecánico (§2–3).

### 2.1 Tabla de correspondencia Laravel → Python (§97)

| Laravel Feature | Python Component | Database Entity | API Endpoint | Tests | Status |
|---|---|---|---|---|---|
| `routes/adms.php` (5 rutas) | `backend/app/adms/router.py` | — | `GET/POST /iclock/cdata`, `GET/POST /iclock/registry`, `GET /iclock/getrequest`, `POST /iclock/devicecmd`, `GET /iclock/inspect` | `tests/integration/test_adms_*.py` | ✅ diseñado |
| `ValidateDeviceRequest` middleware (SN + body limit) | `backend/app/adms/validators.py` + dependencia FastAPI `require_device` | — | todos `/iclock/*` (413 / 400 / 503) | fixtures `invalid serial`, `oversized payload` | ✅ diseñado |
| `AdmsController::handleRegistry` | `services/device.py::register_device` + `adms/router.py::handle_registry` | `devices` (+ `device_events`) | `POST /iclock/registry` | `test_registry.py` | ✅ diseñado |
| `AdmsController::handleAttLog` | `adms/parser.py::parse_attlog` + `services/attendance.py::ingest` | `attendance_logs` + `adms_payloads` | `POST /iclock/cdata?table=ATTLOG` | `test_cdata_attlog.py` + idempotencia | ✅ diseñado |
| `AdmsController::handleUserInfo` | `adms/parser.py::parse_userinfo` + `services/device_user.py::sync_from_device` | `device_users` | `POST /iclock/cdata?table=USERINFO` | `test_cdata_userinfo.py` | ✅ diseñado |
| `OPERLOG` branch → `OK` | misma rama en `adms/router.py` | — (solo `adms_payloads` + evento) | `POST /iclock/cdata?table=OPERLOG` | incluido en cdata tests | ✅ diseñado |
| `handleInfoOrCommands` (KV `\n` + drain) | `adms/parser.py::parse_device_info` + `services/command.py::drain_for_device` | `devices.last_device_info` + `device_commands` | `POST/GET /iclock/cdata` sin tabla | `test_cdata_info.py` | ✅ diseñado |
| `AttendanceParser::parseAttendanceRecords` | `backend/app/adms/parser.py` (puro, sin I/O) | — | — | `tests/unit/test_parser_attlog.py` | ✅ diseñado |
| `AttendanceParser::parseUserRecords` | `backend/app/adms/parser.py` | — | — | `tests/unit/test_parser_userinfo.py` | ✅ diseñado |
| `AttendanceParser::parseKVPairs` + `trimTildePrefix` | `parse_kv_pairs()` + `parse_registry_body()` | — | — | `tests/unit/test_parser_kv.py` | ✅ diseñado |
| `AttendanceParser::parseCommandResults` (batched + shell/multiline) | `parse_command_results()` | — | — | `tests/unit/test_parser_cmdresult.py` | ✅ diseñado |
| `AttendanceParser::validateSerialNumber` | `validators.validate_serial_number` (`^[A-Za-z0-9_-]{1,64}$`) | — | — | unit | ✅ diseñado |
| `CommandManager::queue/drain/confirm` + wire `C:<id>:<cmd>` | `services/command.py::CommandManager` + `adms/commands.py::CommandBuilder` | `device_commands` | `GET /iclock/getrequest`, `POST /iclock/devicecmd` | `test_getrequest.py`, `test_devicecmd.py`, concurrencia `SKIP LOCKED` | ✅ diseñado |
| `sendUserAddCommand` (`DATA UPDATE USERINFO`, NO `USER ADD`) | `CommandBuilder.update_userinfo()` | `device_commands` | vía `POST /api/v1/commands` (whitelist) | unit + integración | ✅ diseñado |
| `sendUserDeleteCommand` (`DATA DELETE USERINFO`, NO `DATA DEL`) | `CommandBuilder.delete_userinfo()` | `device_commands` | idem | unit + integración | ✅ diseñado |
| `sendQueryUsersCommand` (`DATA QUERY USERINFO`) | `CommandBuilder.query_userinfo()` | `device_commands` | idem | unit | ✅ diseñado |
| `sendGetOptionCommand` (`GET OPTION FROM <key>`, 16 keys) | `CommandBuilder.get_option()` + `GET_OPTION_KEYS` whitelist | `device_commands` | idem | unit | ✅ diseñado |
| `sendShellCommand` | **NO implementado** — `SHELL = DISABLED` (§42) | — | sin endpoint | test de rechazo | ✅ diseñado |
| `sendInfoCommand` / `sendCheckCommand` / `sendLogCommand` | `CommandBuilder.info()/check()/log()` | `device_commands` | whitelist | unit | ✅ diseñado |
| `DeviceManager::register/updateActivity/isOnline` (threshold 120s) | `services/device.py` (derivado de `last_activity_at`, sin columna `online`) | `devices` | `GET /api/v1/devices` (estado derivado) | `test_online_offline.py` | ✅ diseñado |
| `EvictStaleDevicesCommand` (delete tras 24h) | **NO eviction física** — estados `online/offline/stale/disabled` (§46); cleanup solo vía tarea Celery opt-in que marca `stale`, nunca borra | `devices.status` | — | unit | ✅ diseñado |
| `ZktecoDevice` (id, serial, last_activity, options, timezone) | `models/device.py` extendido (§12–13) | `devices` | — | migración | ✅ diseñado |
| `ZktecoAttendanceLog` | `models/attendance.py` extendido (§16–18) | `attendance_logs` | `GET /api/v1/attendance` | migración + idempotencia | ✅ diseñado |
| `ZktecoCommandLog` | `models/command.py` extendido (§19–21) | `device_commands` | `GET /api/v1/commands` | migración | ✅ diseñado |
| Events (`AttendanceReceived`, `DeviceRegistered`, `DeviceInfoReceived`, `CommandResultReceived`, `UserQueryReceived`) | `models/device_event.py` persistidos + dispatch interno (`services/events.py`) | `device_events` | visibles en `GET /api/v1/devices/{id}/events` | integración | ✅ diseñado |
| `config/zkteco-adms.php` | `core/config.py` (`ZKTECO_*` env) | — | — | — | ✅ diseñado |

### 2.2 Decisiones deliberadas donde divergimos de Laravel

1. **UUID como PK pública** + `protocol_command_id BIGINT` para el wire (§6, §21).
   Laravel usa autoincrement como wire ID; nosotros desacoplamos identidad
   interna (UUID) de identidad de protocolo (entero monotónico por dispositivo
   vía secuencia dedicada) para permitir particionado y exposición segura.
2. **Sin borrado de dispositivos** (§45–46, §88–89): `status` derivado +
   `disabled` administrativo. Laravel evicta tras 24h; nosotros conservamos
   historial (asistencia/comandos/eventos/auditoría).
3. **`adms_payloads`** (§17): Laravel no persiste el body crudo; nosotros lo
   persistimos siempre (hash SHA-256, `processing_status`) para debugging de
   firmwares reales y reconstrucción de fallos.
4. **Idempotencia ATTLOG** (§18): constraint único
   `(device_id, device_user_pin, recorded_at, status, verify_mode, work_code)`
   + `ON CONFLICT DO NOTHING` por lote; Laravel insertaba sin dedup.
5. **Concurrencia en `getrequest`** (§43): `SELECT … FOR UPDATE SKIP LOCKED`;
   Laravel hacía `drain` sin lock (doble entrega ante polls simultáneos).
6. **`device_users` + `audit_logs` + RBAC + JWT RS256 + Redis**: no existen en
   Laravel; son extensión administrativa propia (§7–11, §14, §23, §48–51).

---

## 3. Estructura del backend (§5)

```text
backend/
├── app/
│   ├── main.py                  # factory create_app(): ADMS + /api/v1 + /health + /ready
│   ├── cli.py                   # createsuperuser (bootstrap operativo, H-02)
│   ├── core/                    # config, database, redis, revocation, ratelimit, security, logging, exceptions, constants
│   ├── api/v1/                  # router, auth, users, devices, resources, deps (+ shims attendance/device_users/commands/audit)
│   ├── adms/                    # router, protocol, parser, serializers, validators, commands, exceptions, schemas
│   ├── models/                  # user (+role/permission/audit), device (+users/attendance/payloads/commands/events), types, base
│   ├── repositories/            # acceso a datos por agregado (sin lógica de negocio)
│   ├── services/                # auth, device, attendance, device_user, command, audit, events
│   └── workers/                 # celery_app + tasks (reports, exports, maintenance)
├── alembic/                     # env.py + script.py.mako + versions/ (H-03: única vía de esquema, §86)
├── tests/                       # unit (sqlite) + integration (sqlite + PG via ZKTECO_TEST_PG_URL) + fixtures
├── pyproject.toml               # deps + ruff + mypy strict + pytest + coverage>=90
├── Dockerfile                   # copia app + alembic completo (incl. versions/)
└── .env.example
```

Reglas de dependencia: `api/adms → services → repositories → models`.
`adms/parser.py` y `adms/commands.py` son **puros** (sin I/O ni DB) para
testearse al >90% sin infraestructura. Prohibido estado global mutable (§69).

---

## 4. Modelo de datos (resumen; detalle en `docs/DATABASE.md`)

Tablas: `users`, `roles`, `permissions`, `user_roles`, `role_permissions`,
`devices` (+`command_seq`), `device_users` (+`sync_state`/`pending_op`),
`attendance_logs`, `adms_payloads`, `device_commands`, `device_events`,
`audit_logs`. PostgreSQL obligatorio (§6), UUID PK (§6), `JSONB`/`INET`/
`TIMESTAMPTZ` propios (§87), FKs nombradas (`fk_*`) + uniques nombradas
(`uq_*`) + checks + índices del §24 (redundantes eliminados en L-02).
`work_code` normalizado a `""` para que el constraint de dedup sea efectivo.
Comandos con TTL (`expires_at`, default 24h) y `max_attempts` (default 10,
reintento en fallo hasta agotar). Sin particionado inicial, pero
`attendance_logs` diseñada para particionar por `recorded_at` (§25). Sin
soft-delete salvo `users.is_active` y `devices.status='disabled'` (§88–89).
Migraciones `0001_initial` + `0002_lifecycle`, `alembic check` limpio.

---

## 5. ADMS (resumen; detalle en `docs/ADMS_PROTOCOL.md`)

Pipeline `cdata` (§30): `raw → validate device → throttle → persist payload →
classify → parse → DTO → validate → service → DB → event → ADMS response`.
Respuestas `text/plain` exactas (`OK`, `OK: N`, `C:<id>:<cmd>\n`, `ERROR` en
fallo de persistencia); nunca JSON al reloj (§66). Malformados:
skip+log+counter+payload, sin abortar el lote (§32). Timezone por dispositivo
(gestionable vía `PATCH /api/v1/devices/{id}`, validado con `ZoneInfo`),
`TIMESTAMPTZ` UTC interno, nunca naive (§47). Límites: body 10MB (§53), 1000
dispositivos (§54, enforcement atómico con advisory lock), 100
comandos/dispositivo (§55). `protocol_command_id` monotónico por dispositivo
vía counter atómico `UPDATE…RETURNING` (nunca MAX+1). `inspect` deshabilitado
por defecto (§26). Semántica de fallos (M-04): persistencia de datos del
reloj fallida → `500`+`ERROR` (el reloj reintenta); `getrequest`/`devicecmd`
fallidos → `OK` (nada propiedad del reloj se pierde; confirms idempotentes).
`table=` insensible a mayúsculas. Adaptador
`DeviceProtocol → ZKTecoADMSProtocol` para futuros protocolos (§77).

---

## 6. Seguridad (resumen; detalle en `docs/SECURITY.md`)

JWT RS256 con claims `sub/iat/exp/jti/type/iss/aud`, tipos
`access/refresh`, validación de firma+issuer+audience+expiración+tipo+algoritmo
(§48–49); revocación de `jti` en Redis **compartido (sin fallback local)**;
logout revoca access+refresh (§51, M-01). Passwords Argon2id (§50, mín. 10 en
API/CLI). Comandos solo vía `CommandType` enum + `CommandBuilder` validado;
CRLF rechazado (§80–81); SHELL deshabilitado (§42). Rate limiting Redis
distribuido: login (IP+cuenta, 429+`Retry-After`), refresh, lockout de cuenta
(L-06), throttle ADMS por serial/IP fail-open (§52, H-01); auth fail-closed
(503 sin Redis). RBAC por permiso en cada endpoint + CRUD de usuarios con
guardas anti-escalado/último-admin (§91, H-02); auditoría de acciones
relevantes (§63, §23). Secretos nunca en `NEXT_PUBLIC_*` (§92); tokens del
frontend solo en memoria (documentado). `request_id` real en envelope de
error, logs y `X-Request-ID` (§82); 422 sanitizados (sin paths internos);
CORS explícito (nunca `*`+credenciales); headers base en app, TLS/HSTS/CSP en
proxy; `X-Forwarded-For` solo de proxies confiables; `Password=` de USERINFO
redactado en `raw_body` (hash sobre bytes originales); `/ready` sanitizado;
ADMS fuera de OpenAPI; `/docs` desactivable.

---

## 7. Fases y aceptación

Fases §96–106: 0 reverse ✓ → 1 DB ✓ → 2 ADMS core ✓ →
3 prueba con dispositivo real (**PENDIENTE: sin hardware, NOT VERIFIED**) →
4 comandos ✓ → 5 auth ✓ → 6 admin API ✓ → 7 Next.js ✓ (build verificado,
sin hardware) → 8 security review ✓ (AUDIT_REPORT.md + remediación) → 9 QA ✓.
Supuestos registrados en `docs/SECURITY.md`: despliegue single-tenant (sin
autorización por objeto), TLS/headers/CSP en reverse proxy, Redis compartido
obligatorio para auth, `Password=` redactado con hash íntegro, retry ADMS
asumido ante `500`/`ERROR`. Criterios §107 y quality gate §93–94
(ruff+mypy strict+pytest+coverage≥90; frontend eslint+typecheck+build).
