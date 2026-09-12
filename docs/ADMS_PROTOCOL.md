# ADMS PROTOCOL — ZKTeco Push HTTP (referencia implementativa)

Derivado del estudio funcional de `athwari/laravel-zkteco-adms-server`
(config, routes, DTOs, Enums, Events, Http, Models, Services, tests).
Ante duda: repositorio → tests → código → documentar incertidumbre →
fixture → implementar → validar contra dispositivo real (§75).
Objetivo prioritario: **SpeedFace-V5LP** (§76).

## 1. Endpoints (§26)

```text
GET  /iclock/cdata?SN=<serial>[&table=ATTLOG|OPERLOG|USERINFO]
POST /iclock/cdata?SN=<serial>[&table=...]        (body = payload)
GET  /iclock/registry?SN=<serial>
POST /iclock/registry?SN=<serial>                 (body = registry KV)
GET  /iclock/getrequest?SN=<serial>               (poll de comandos)
POST /iclock/devicecmd?SN=<serial>                (confirmaciones)
GET  /iclock/inspect                             (debug JSON, deshabilitado por defecto, §26)
```

- ADMS **sin JWT** (§27). Autenticación = validación de `SN` + registro.
- `SN` ausente → `400 Missing SN parameter`. `SN` inválido → `400 Invalid SN parameter`.
- Validación: `^[A-Za-z0-9_-]{1,64}$` (§28). Rechaza SQL/CRLF/control/path-traversal
  por construcción (solo charset permitido).
- Límite de body: `ZKTECO_MAX_BODY_SIZE=10485760` (10MB, §53). Superarlo → `413`.
  Se chequea `Content-Length` y tamaño real en POST.
- Límite de dispositivos: `ZKTECO_MAX_DEVICES=1000` (0 = ilimitado, §54).
  Superarlo al registrar uno nuevo → `503 Device limit reached` (transaccional).
- Todo request válido hace `registerDevice(sn)` (idempotente) + `updateActivity(sn)`
  antes de la lógica específica (igual que `requireDevice` en Laravel).

## 2. Respuestas wire (texto exacto, §66)

| Caso | Respuesta `text/plain` |
|---|---|
| Sin comandos pendientes (getrequest / cdata handshake) | `OK` |
| Push-options handshake (`GET /iclock/cdata?...&options=all`) | Bloque `GET OPTION FROM:` + `TransFlag`/`Realtime` (CRLF, §26; **sin** líneas `C:`, que solo viajan en getrequest) |
| ATTLOG procesado, N válidos | `OK: N` |
| OPERLOG | `OK` |
| USERINFO / registry / devicecmd / device-info | `OK` |
| Con K comandos pendientes | `C:<protocol_id>:<command>\n` × K |
| Fallo de persistencia (cdata/registry) | `500` + `ERROR` (reintentar) |
| Fallo de entrega/confirmación | `200` + `OK` (idempotente, reintentar) |
| inspect deshabilitado | `404 Not Found` |
| Errores | `400` / `413` / `503` con mensaje corto de texto |

Jamás JSON al reloj. `GET OPTION FROM <k>` y `DATA ...` viajan dentro de
líneas `C:<id>:...`. `table=` insensible a mayúsculas. Semántica de fallos
(M-04): solo se responde `OK` cuando el estado está a salvo; si los datos del
reloj pueden haberse perdido se responde `500`+`ERROR` para forzar reintento
(contract documentado; el reintento exacto depende del firmware).

## 3. `registry` (§29, §35)

1. `SN` → validar → `register_device` (crea si no existe, detecta re-registro) →
   `last_registry_at`, `last_activity_at` → persistir `adms_payloads` →
   parsear body → merge `options` + columnas normalizadas → evento
   (`device_registered` / `device_re_registered`) → `OK`. Idempotente.
2. Formato body: pares `key=value` separados por **coma**, con posible prefijo
   `~` en claves (`~DeviceName=SpeedFace,~FWVersion=Ver 1.1.17,...`).
   Parser: `parse_registry_body()` = `parse_kv_pairs(sep=",", key_transform=trim "~")`.
3. No asumir equivalencia con device-info (§35): parsers separados con núcleo común.

## 4. `cdata` (§30–34)

Clasificación por query `table`:

- `ATTLOG` → §4.1. Respuesta `OK: N`.
- `OPERLOG` → `OK` (se persiste payload + evento `operlog_received` a nivel `debug`).
- `USERINFO` → §4.3. Respuesta `OK`.
- ausente/otro → device-info (§4.4) en POST + drenar comandos (igual que getrequest).
- EXCEPCIÓN: con query `options=all` (handshake de opciones del firmware, §26)
  se responde el bloque push-options y NO se drenan comandos: varios firmwares
  acc ignoran cuerpos mezclados y jamás suben tablas. TransFlag configurable vía
  `ZKTECO_TRANS_FLAG` (bits sin verificar en hardware).

Pipeline (§30): `raw → validate → payload classify → parser → DTO →
validation → service → DB → event → response`.

### 4.1 ATTLOG (§31–32)

Línea: `USER_ID<TAB>TIMESTAMP<TAB>STATUS<TAB>VERIFY_MODE<TAB>WORK_CODE`.
Mínimo `UserID + timestamp`; resto con defaults (`status=0`, `verify_mode=0`,
`work_code=''`). Campos no enteros → default `0` + warning (no abortar).
Timestamps aceptados: `Y-m-d H:i:s` (interpretado en timezone del dispositivo)
o entero epoch Unix. `UserID` vacío o timestamp inválido → skip + log +
contador `malformed`, **sin insertar NULL ni inventar fechas** (§32);
el resto del lote continúa. Persistencia por lote con `ON CONFLICT DO NOTHING`
sobre la clave de idempotencia (§18). Respuesta `OK: <válidos>`.
Timezone: `devices.timezone`, fallback `ZKTECO_DEFAULT_TIMEZONE=UTC`;
interno `TIMESTAMPTZ` UTC; nunca naive (§47).

Ejemplo:

```text
1001\t2024-03-15 08:30:00\t0\t1\t
1002\t2024-03-15 08:31:00\t1\t4\tWC01
```

### 4.2 Enums

`AttendanceStatus`: 0 CheckIn, 1 CheckOut, 2 BreakOut, 3 BreakIn,
4 OvertimeIn, 5 OvertimeOut (desconocido → `Unknown (n)`).
`VerifyMode` (ADMS push, ≠ TCP 4370): 0/3 Password, 1 Fingerprint, 2/4 Card,
5 Fp+Card, 6 Fp+Pwd, 7 Card+Pwd, 8 Card+Fp+Pwd, 9 Other, 15 Face, 25 Palm.

### 4.3 USERINFO (§33, §15)

Línea: campos `key=value` separados por TAB, ej.
`PIN=1\tName=John\tPrivilege=0\tCard=\tPassword=`.
Campos: `PIN` (obligatorio; sin PIN → skip), `Name`, `Privilege` (int, default 0;
14 = admin), `Card`, `Password`. Upsert por `(device_id, pin)`; un push del
reloj confirma intents pendientes del mismo PIN (reconciliación M-03).
**`Password=` NO es password administrativo**: no se muestra en frontend, no se
loguea; por defecto **NO se persiste** (`persist_device_password=false`).
Si se habilita, va a `device_users.device_password` con justificación y
sanitización de logs (§15, §83). Independientemente, `adms_payloads.raw_body`
siempre redacta `Password=***` (hash SHA-256 sobre bytes originales).

### 4.4 Device info (§34)

Body POST `key=value` separado por newline, ej.
`DeviceName=...\nFWVersion=...\nIPAddress=...\nMACAddress=...\nPlatform=...`.
Se guarda raw en `devices.last_device_info` + merge en `options` +
normalización (§13): `name ← DeviceName`, `firmware_version ← FWVersion`,
`ip_address ← IPAddress`, `mac_address ← MACAddress`, `platform ← Platform`.
Evento `device_info_received`. Contadores visibles en dashboard (§59):
`UserCount, FPCount, FaceCount, AttLogCount, TransactionCount,
MaxUserCount, MaxAttLogCount, MaxFingerCount, MaxFaceCount` (permanecen en
`options` aunque no tengan columna).

## 5. `getrequest` (§43)

`validate → select pending (FOR UPDATE SKIP LOCKED) → mark sent →
wire`. Dos polls concurrentes del mismo dispositivo jamás reciben el mismo
comando. Se entregan **todos** los pendientes ordenados por
`protocol_command_id` (igual que `drainCommands` de Laravel, más lock).

## 6. `devicecmd` (§44)

Body con dos formatos (ambos soportados):

- Batch: `ID=1&Return=0&CMD=INFO\nID=2&Return=0&CMD=CHECK\n`
- Shell/multilínea: `ID=32\nReturn=0\nCMD=Shell\nContent=...`
  Parser: normaliza `\n`→`&`, acumula KV; cada nuevo `ID=` vuelca el resultado
  anterior. `ID` no entero → warning + skip. Campos: `ID`, `RETURN`/`Return`,
  `CMD`. Correlación por `device_commands.protocol_command_id`
  (+ `device_id`). Actualiza `status` (`0 → confirmed`, otro → `failed`),
  `return_code`, `confirmed_at`, `response`. Evento `command_confirmed` /
  `command_failed`. IDs desconocidos → warning, `OK` igualmente. Respuesta `OK`.

## 6b. Ciclo de vida de usuarios del reloj (M-03)

La API escribe *intención* (`sync_state=pending`, `pending_op`), nunca verdad
del reloj: crear → `pending`; confirmar éxito → `synced`; fallar → `failed`;
borrar → `pending` y la fila desaparece solo al confirmar; `PUT` edita +
recola. Eventos `user_sync_confirmed`/`user_sync_failed`. Ver §61.

## 7. Comandos soportados (§37–41) — whitelist estricta

```text
INFO                                  → INFO
CHECK                                 → CHECK
LOG                                   → LOG
DATA QUERY USERINFO                   → query users (respuesta vía cdata USERINFO)
GET OPTION FROM <key>                 → 16 keys: DeviceName, FWVersion, IPAddress,
                                       MACAddress, Platform, WorkCode, LockCount,
                                       UserCount, FPCount, AttLogCount, FaceCount,
                                       TransactionCount, MaxUserCount, MaxAttLogCount,
                                       MaxFingerCount, MaxFaceCount
DATA UPDATE USERINFO PIN=<pin>\tName=<n>\tPrivilege=<p>\tCard=<c>
                                      → alta/edición (NO "USER ADD", §38)
DATA DELETE USERINFO PIN=<pin>        → baja (NO "DATA DEL", §39)
```

Construcción solo vía `CommandBuilder` + `CommandType` enum con validación
CRLF (`\r`/`\n` → `InvalidCommandError`, §81). `SHELL` deshabilitado sin
endpoint (§42). Wire: `C:<protocol_command_id>:<command>\n` (§44: `CommandEntry::toWireFormat`).

## 8. Online/offline/stale (§45–46)

Sin columna `online`. Derivado de `last_activity_at` vs `now()` con
`ZKTECO_ONLINE_THRESHOLD=120` (s): `online` si `≤ threshold`, `offline` si
`> threshold`, `stale` si `> 24h` (configurable), `disabled` solo manual.
**Nunca borrar dispositivos automáticamente** (divergencia Laravel §46);
borrado físico prohibido con historial → usar `disabled` (§89).

## 9. Incertidumbres registradas (validar con SpeedFace-V5LP real, §75)

1. Cuerpo exacto de `registry` del V5LP (¿claves con `~`? ¿qué opciones envía?).
   → fixture `registry` + captura de `adms_payloads`.
2. `table=` exacto que usa el V5LP para ATTLOG/USERINFO y si envía `Stamp`,
   `OpStamp` u otros params extra en query.
3. Formato de `devicecmd` para respuestas `DATA QUERY`/`GET OPTION`
   (¿vuelven por `devicecmd` o por `cdata`? Laravel asume USERINFO por cdata).
4. Valores reales de `VerifyMode`/`Status` del V5LP (firmware-dependientes).
