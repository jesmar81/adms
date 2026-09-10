# SECURITY

Revisión explícita obligatoria (§79, §105): SQL/command/ADMS/CRLF injection,
oversized, JWT confusion/replay/refresh abuse, rate limiting, escalado,
IDOR, suplantación de dispositivo/serial spoofing, bypass de auditoría.
Estado: remediación 2026-09-10 (ver REMEDIATION_REPORT.md).

## 1. Auth administrativa (§48–51)

- JWT **RS256 únicamente** (§48). `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` (PEM);
  privada nunca en Git/frontend/logs/DB (§49). Lecturas de fichero cacheadas
  en proceso (rotación = reinicio). Backend firma y valida; arquitectura lista
  para separar issuer/verifier.
- Claims obligatorios: `sub, iat, exp, jti, type, iss, aud`;
  tipos `access` (15 min) / `refresh` (7 días). Validar firma, issuer,
  audience, expiración, tipo y algoritmo (rechazar `alg=none`/HS256 →
  anti-confusion, §79).
- Refresh con revocación en **Redis compartido** por `jti` (§51, sin fallback
  local): `logout` revoca access+refresh (terminación efectiva de sesión);
  rotación del refresh en cada uso; expiración como respaldo. Nunca confiar
  solo en `exp`. **Sin Redis, auth responde 503 (fail-closed)** — Redis es
  dependencia dura de autenticación.
- Passwords **Argon2id** (§50) en `users.password_hash` (mín. 10 caracteres en
  API/CLI). Nada en claro. Bootstrap solo vía `python -m app.cli
  createsuperuser` (getpass/env, auditado); gestión vía `/api/v1/users` con
  guardas (sin auto-escalado, sin auto-borrado, último superuser protegido).
- Rate limiting Redis distribuido (§52, H-01): login 10/min por IP **y** por
  cuenta (429 + `Retry-After` + envelope `RATE_LIMITED`); refresh 30/min/IP;
  lockout de cuenta tras 20 fallos/15min (L-06); ADMS 600/min por serial y
  3000/min por IP (fail-open documentado, 429 texto plano).

## 2. ADMS (§27–28, §52–53, §80–81)

- Sin JWT; identificación por `SN` validado `^[A-Za-z0-9_-]{1,64}$`.
- Comandos solo whitelist vía `CommandType` + `CommandBuilder` con parámetros
  validados (§80). Frontend jamás envía texto libre al reloj.
- CRLF: cualquier campo hacia el wire con `\r`/`\n` → rechazo (§81).
- `SHELL` deshabilitado sin endpoint (§42); reactivarlo exige revisión
  independiente.
- `Password=` de USERINFO (§19): no frontend, no logs, no columna salvo flag;
  en `adms_payloads.raw_body` se almacena **redactado** (`Password=***`) con
  el SHA-256 calculado sobre los bytes originales (trazabilidad sin secreto).
- `table=` insensible a mayúsculas; `inspect` deshabilitado en producción (§26).
- Fallos de persistencia de datos del reloj → `500`+`ERROR` (reintento);
  `getrequest`/`devicecmd` fallidos → `OK` (idempotentes, nada se pierde).

## 3. Autorización y auditoría (§63, §91)

Cada endpoint `/api/v1/*` exige usuario autenticado **+ permiso** (`devices.read`…).
401 sin token / 403 sin permiso. Modelo single-tenant asumido: no hay
autorización por objeto/fila (cualquier holder del permiso accede a cualquier
UUID); documentado como decisión, no como IDOR.
Toda acción relevante → `audit_logs` con `user_id, action, resource, device_id,
ip, user_agent, request_id` (§23): `login[.failed]`, `logout`, `user.*`,
`device.update`, `device.command`, `device_user.*`. IPs de auditoría usan el
peer directo salvo proxies configurados en `TRUSTED_PROXIES_RAW`.

## 4. Datos y transporte

- TLS terminating reverse-proxy en producción (el backend no termina TLS).
  HSTS solo con `HSTS_ENABLED=true` (tras el proxy). App envía
  `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `X-Request-ID`.
  CSP y resto de cabinas, en el proxy (ver `docker-compose.yml` + despliegue).
- CORS: solo orígenes explícitos `FRONTEND_ORIGINS_RAW` (nunca `*` + credenciales);
  vacío = sin CORS (fail-closed para navegadores).
- Tokens del frontend **solo en memoria** (sin localStorage/sessionStorage):
  un XSS no puede exfiltrar sesión persistente; recargas requieren re-login.
  Migración a cookies httpOnly documentada como follow-up.
- Secretos solo env (`DATABASE_URL`, `REDIS_URL`, `JWT_PRIVATE_KEY[_FILE]`);
  `NEXT_PUBLIC_*` jamás con secretos (§92). Solo `NEXT_PUBLIC_API_URL` (origen
  del API, no secreto).
- Logs structlog con `request_id` real (también en envelopes de error y
  `X-Request-ID`); sanitizar `password, JWT, refresh_token, private_key,
  device_password`; 422 sanitizados (sin paths/funciones internas); `/ready`
  solo booleanos; `/docs` desactivable (`DOCS_ENABLED=false` en prod).
- ADMS fuera de OpenAPI (`include_in_schema=False`).

## 5. Checklist de revisión (§79) — estado post-remediación

- [x] SQLi (ORM + parámetros; `SN` por charset; sin SQL dinámico)
- [x] Command injection (whitelist + CRLF + tests)
- [x] ADMS injection (parsers tolerantes, skip+log, `table` case-insensitive)
- [x] CRLF/wire injection (validación + tests)
- [x] Oversized (10MB + tests 413; chunked tras throttle por serial)
- [x] JWT confusion/replay/refresh abuse (tests incl. rotación y logout total)
- [x] Rate limiting (Redis + tests 429/lockout/fail-closed/fail-open)
- [x] Priv-esc / self-target / último-admin (tests RBAC + guards)
- [ ] Spoofing de serial (sin secreto compartido en MVP → documentado;
      endurecer con allowlist/IP si el despliegue lo permite)
- [x] Audit bypass (emisión testeada en login/comandos/usuarios/dispositivos)
