# DATABASE

PostgreSQL obligatorio (§6). Sin SQLite en producción. Migraciones Alembic
exclusivas (§86), ejecutables desde cero (`backend/alembic/versions/`,
`alembic upgrade head` + `alembic check` limpios en PG). Tipos propios:
`UUID`, `JSONB`, `INET`, `TIMESTAMPTZ` (§87). FKs nombradas (`fk_*`) +
uniques nombradas (`uq_*`) + checks + índices (§24, §87). Convención de
nombres FK en `Base.metadata` para paridad exacta migración↔modelos.

## 1. Tablas

### `users` (§7) — administradores (≠ `device_users`)

```text
id UUID PK | username VARCHAR(100) UNIQUE NOT NULL | email VARCHAR(255) UNIQUE NOT NULL
password_hash TEXT NOT NULL (Argon2id) | first_name, last_name VARCHAR(100)
is_active BOOLEAN DEFAULT true | is_superuser BOOLEAN DEFAULT false
last_login_at TIMESTAMPTZ NULL | created_at, updated_at TIMESTAMPTZ NOT NULL
```

Desactivar vía `is_active` (§88); no borrado físico con auditoría.

### `roles` (§8), `permissions` (§9), `user_roles` (§10), `role_permissions` (§11)

`roles(id UUID PK, name VARCHAR(50) UNIQUE, description, created_at, updated_at)`.
`permissions(id UUID PK, code VARCHAR(100) UNIQUE, description, created_at, updated_at)`.
Seed inicial solo roles+permisos (§98): `admin` (todos), `operator`
(`devices.read/write, attendance.read/export, device_users.*, commands.read/execute`),
`viewer` (`*.read` + `attendance.export`). Códigos §9
(`devices.read/write/delete`, `attendance.read/export`, `device_users.read/write/delete`,
`commands.read/execute`, `users.read/write/delete`, `audit.read`).

### `devices` (§12–13)

Columnas normalizadas + `options JSONB` (GET OPTION) + `last_registry_payload` /
`last_device_info` JSONB + `metadata JSONB`. Status check
`unknown|online|offline|stale|disabled` — `online/offline/stale` derivados de
`last_activity_at` (threshold 120s, §45); `disabled` manual (§89).
Timestamps de ciclo: `registered_at`, `last_registry_at`, `last_cdata_at`,
`last_command_poll_at`, `last_command_result_at`, `last_activity_at`.
Normalización desde opciones (§13): `name`, `firmware_version`, `platform`,
`ip_address` (INET), `mac_address`.

### `device_users` (§14–15) — personas del reloj (≠ `users`)

`(id UUID PK, device_id FK→devices CASCADE, pin VARCHAR(64), name,
privilege INT DEFAULT 0, card_number NULL, device_password NULL,
enabled DEFAULT true, raw_data JSONB, last_synced_at NULL,
sync_state [synced|pending|failed] (M-03: intent vs confirmado),
pending_op JSONB NULL, last_protocol_command_id BIGINT NULL,
created_at, updated_at)`,
`UNIQUE(device_id, pin)` + CHECK sync_state. `device_password`: NO persistir
por defecto (§15); `raw_data` nunca incluye `Password=`.

### `attendance_logs` (§16, §18, §25)

`(id UUID PK, device_id FK NOT NULL, device_user_id FK NULL SET NULL,
device_user_pin VARCHAR(64) NOT NULL, recorded_at TIMESTAMPTZ NOT NULL,
device_timezone NULL, status INT DEFAULT 0, verify_mode INT DEFAULT 0,
work_code VARCHAR(32) NULL, raw_line TEXT NULL, raw_payload_id FK NULL,
source DEFAULT 'adms', received_at NOT NULL, created_at NOT NULL)`.
Idempotencia (§18): `UNIQUE(device_id, device_user_pin, recorded_at, status,
verify_mode, work_code)` + dedup SELECT masivo + `ON CONFLICT DO NOTHING` +
`RETURNING` (M-05, chunks de 1000 por el techo de 65535 binds de PG).
`work_code` normalizado a `""` (default Laravel) para que el constraint sea
efectivo (los NULL nunca son iguales en UNIQUE). Índice
`(device_id, recorded_at)` (§24, §60; el duplicado DESC se eliminó en L-02:
el btree simple sirve scans DESC). Diseñada para futuro particionado por
`recorded_at` (§25).

### `adms_payloads` (§17, §67)

`(id UUID PK, device_id FK NULL, endpoint VARCHAR(50), data_type NULL,
content_type NULL, headers JSONB NULL, query_params JSONB NULL, raw_body TEXT NULL,
body_hash VARCHAR(64) SHA-256, received_at, processing_status
[received|processed|partial|failed], processed_at NULL, error_message NULL)`.
Se persiste **antes** de parsear; nunca se pierde el body crudo.

### `device_commands` (§19–21)

`(id UUID PK, device_id FK, protocol_command_id BIGINT NOT NULL,
command_type VARCHAR(50), command TEXT, payload JSONB NULL,
status [pending|sent|confirmed|failed|expired|cancelled],
return_code NULL, queued_at, sent_at NULL, confirmed_at NULL, expires_at NULL,
attempt_count DEFAULT 0, last_attempt_at NULL, response TEXT NULL,
error_message NULL, created_by FK users NULL, created_at, updated_at)`,
`UNIQUE(device_id, protocol_command_id)`. `protocol_command_id`: entero
monotónico por dispositivo vía counter atómico `devices.command_seq`
(`UPDATE…RETURNING`, M-08); nunca UUID en el wire (§21). Ciclo de vida
(L-02): `expires_at` (= queued + `ZKTECO_COMMAND_TTL`, 24h) → `expired`;
fallo con intentos restantes → recola (`pending`, evento `command_retry`);
agotados (`ZKTECO_COMMAND_MAX_ATTEMPTS`, 10) → `failed`. `pendingCount`
cuenta `pending` (+`sent` no confirmados para el límite de cola).

### `device_events` (§22)

`(id UUID PK, device_id FK, event_type VARCHAR(80), severity DEFAULT 'info',
payload JSONB DEFAULT '{}', created_at)`. Tipos §22 más ciclo de usuario (`user_sync_confirmed`, `user_sync_failed`)
y `command_retry` (`device_registered`, `device_re_registered`,
`device_online/offline`, `attendance_received`, `device_info_received`,
`user_query_received`, `command_queued/sent/confirmed/failed`,
`adms_error`, `operlog_received`).

### `audit_logs` (§23, §63)

`(id UUID PK, user_id FK NULL, action VARCHAR(100), resource_type NULL,
resource_id UUID NULL, device_id FK NULL, ip_address INET NULL, user_agent NULL,
request_id NULL, metadata JSONB DEFAULT '{}', created_at)`.
Acciones §63 (`login[.failed]`, `logout`, `user.create/update/delete`,
`device.update`, `device.command`, `device_user.create/update/delete`).

## 2. Índices (§24)

`devices(serial_number UNIQUE, status, last_activity_at)`,
`attendance_logs(device_id, device_user_pin, recorded_at, status, verify_mode,
(device_id, recorded_at DESC))`, `device_users(device_id, (device_id,pin))`,
`device_commands(device_id, status)` (+ unique backstop; el índice redundante
`(device_id, protocol_command_id)` se eliminó en L-02),
`device_events(device_id, event_type, created_at)`,
`audit_logs(user_id, device_id, created_at)`, `adms_payloads(device_id, received_at)`.

## 3. Transacciones (§68)

ATTLOG por lote (M-05): `BEGIN → user-map (1 SELECT) → dedup masivo
(1 SELECT/chunk) → INSERT masivo + RETURNING (1/chunk) → COMMIT`. Filas fuera
de rango SmallInteger se descartan con warning; el resto nunca aborta.
Registro de dispositivos: `pg_advisory_xact_lock` para el tope
`max_devices` (M-08). `getrequest`: `SELECT … FOR UPDATE SKIP LOCKED` (§43).

## 4. Migraciones

`0001_initial` (12 tablas, constraints nombrados) + `0002_lifecycle`
(`devices.command_seq`, `device_users.sync_state/pending_op/
last_protocol_command_id`). Reglas: un statement por `op.execute()`
(asyncpg rechaza multi-comando), `alembic check` debe salir limpio,
`seed` corre sobre esquema migrado (testeado en PG).
