# DEVELOPMENT

## 1. Requisitos

Python 3.12+ · PostgreSQL 16+ · Redis 7 · Node 24. La suite completa requiere
PostgreSQL y Redis; con Docker se levantan con `docker compose up -d postgres redis`.

## 2. Arranque rápido

```bash
cp backend/.env.example backend/.env
# generar claves RS256:
python - <<'EOF'
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
open('backend/.jwt_private.pem','wb').write(k.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption()))
open('backend/.jwt_public.pem','wb').write(k.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
EOF

docker compose up -d postgres redis          # infra
cd backend && pip install -e ".[dev]" && alembic upgrade head && alembic check
python -m app.seed                            # roles + permisos (§98)
python -m app.cli createsuperuser             # primer admin (H-02, auditado)
uvicorn app.main:app --reload
```

Primer admin, dos caminos equivalentes (misma validación, mismo hash
Argon2id, misma auditoría `user.create`):

```bash
# A) interactivo (recomendado en producción: el password no queda en disco)
python -m app.cli createsuperuser
# B) no interactivo (CI/dev): variables de entorno + --no-input
ZKTECO_ADMIN_USERNAME=admin ZKTECO_ADMIN_EMAIL=admin@example.com \
ZKTECO_ADMIN_PASSWORD='cambia-esto-ya-01' \
  python -m app.cli createsuperuser --no-input
# C) vía seed: con las tres ZKTECO_ADMIN_* definidas (ver backend/.env.example),
#    `python -m app.seed` crea roles, permisos Y el admin en un solo paso
#    (idempotente: un username existente no se toca nunca).
```

`GET http://localhost:8000/health` → `{"status":"ok"}`.
OpenAPI admin: `/docs` (solo `/api/v1/*`; ADMS excluido, §65;
desactivable con `DOCS_ENABLED=false`). La doc de ADMS es
`docs/ADMS_PROTOCOL.md`.

## 3. Variables principales

`ZKTECO_MAX_BODY_SIZE=10485760` · `ZKTECO_ONLINE_THRESHOLD=120` ·
`ZKTECO_STALE_AFTER=86400` · `ZKTECO_MAX_DEVICES=1000` ·
`ZKTECO_MAX_COMMANDS_PER_DEVICE=100` · `ZKTECO_ENABLE_INSPECT=false` ·
`ZKTECO_DEFAULT_TIMEZONE=UTC` · `ZKTECO_COMMAND_TTL_S=86400` ·
`ZKTECO_COMMAND_MAX_ATTEMPTS=10` · `DATABASE_URL` · `REDIS_URL` ·
`JWT_PRIVATE_KEY/PUBLIC_KEY(_FILE)` · `JWT_ISSUER/AUDIENCE` ·
`JWT_ACCESS_TTL=900` · `JWT_REFRESH_TTL=604800` ·
`RATELIMIT_*` (ver `backend/.env.example`) · `TRUSTED_PROXIES_RAW` ·
`FRONTEND_ORIGINS_RAW` · `HSTS_ENABLED` · `DOCS_ENABLED`.
Redis es dependencia dura de auth (sin Redis → 503, fail-closed).

## 4. Flujo de trabajo

Esquema solo vía migraciones (`alembic revision` + `upgrade head` +
`alembic check` limpio, §86); `seed` y `cli` nunca crean esquema.
Calidad §93–94: `ruff check`, `ruff format --check`, `mypy --strict`,
`pytest --cov-fail-under=60` (cobertura medida 63.5%); frontend `npm ci`, `lint`, `typecheck`,
`build`. Ningún agente declara "terminado" solo porque compila; reportar
files/tests/coverage/lint/typing/seguridad.

## 5. Prueba con dispositivo real (§100) — NOT VERIFIED

Apuntar el V5LP (ADMS/Push) a `http://<host>:8000`; verificar registro,
`last_activity_at`, ATTLOG persistido, `getrequest`/`devicecmd` y
`DATA QUERY USERINFO`. Conservar `adms_payloads` de las primeras sesiones
para fixtures. **Sin hardware disponible esta prueba no se declara.**

## 6. Frontend

```bash
cd frontend && npm ci && npm run lint && npm run typecheck && npm run build
```

Tokens solo en memoria (sin localStorage); el backend sigue siendo el
enforcer de permisos. `NEXT_PUBLIC_API_URL` apunta al backend.
