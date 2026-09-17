# ZKTeco ADMS Platform

![CI](https://github.com/jesmar81/adms/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)
![Node](https://img.shields.io/badge/node-24-green?logo=node.js&logoColor=white)
![Next.js](https://img.shields.io/badge/next.js-14-black?logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/fastapi-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/postgresql-16-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/redis-7-DC382D?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white)

Plataforma profesional de control de asistencia para relojes checadores biométricos
ZKTeco (prioridad: **SpeedFace-V5LP**): gateway ADMS con **FastAPI** + **PostgreSQL** +
**Redis** + UI de administración en **Next.js**.

> Referencia funcional (solo protocolo, no es un port):
> `https://github.com/athwari/laravel-zkteco-adms-server`

- Protocolo ADMS: [`docs/ADMS_PROTOCOL.md`](docs/ADMS_PROTOCOL.md)
- Captura de reloj real: [`docs/REAL_DEVICE_CAPTURE.md`](docs/REAL_DEVICE_CAPTURE.md)
- Dominio de personal y asistencia multiempresa: [`docs/HR_ATTENDANCE_DOMAIN_PLAN.md`](docs/HR_ATTENDANCE_DOMAIN_PLAN.md)
- Calendario laboral mexicano y protección de expediente: [`docs/HR_CALENDARS_MX.md`](docs/HR_CALENDARS_MX.md)
- Base de datos: [`docs/DATABASE.md`](docs/DATABASE.md)
- Seguridad: [`docs/SECURITY.md`](docs/SECURITY.md)
- Testing: [`docs/TESTING.md`](docs/TESTING.md)
- Desarrollo: [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)

---

## Tabla de contenidos

1. [Características](#características)
2. [Arquitectura](#arquitectura)
3. [Requisitos](#requisitos)
4. [Puesta en marcha: Docker o manual](#puesta-en-marcha-docker-o-manual)
5. [Instalación en Linux — híbrida](#instalación-en-linux-paso-a-paso)
6. [Instalación en Windows — híbrida](#instalación-en-windows-paso-a-paso)
6. [Configuración](#configuración)
7. [Uso](#uso)
8. [API](#api)
9. [Testing](#testing)
10. [Puertas de calidad](#puertas-de-calidad)
11. [Estructura del proyecto](#estructura-del-proyecto)
12. [Seguridad](#seguridad)
13. [Solución de problemas](#solución-de-problemas)
14. [Contribuir](#contribuir)
15. [Licencia](#licencia)

---

## Características

- **Gateway ADMS** para relojes ZKTeco (`/iclock/registry`, `/iclock/cdata`,
  `/iclock/getrequest`, `/iclock/devicecmd`): registro idempotente, ATTLOG,
  USERINFO, OPERLOG y cola de comandos con confirmación.
- **API de administración** (`/api/v1/*`): dispositivos, asistencia, usuarios del
  reloj, comandos, usuarios, auditoría — con permisos por rol y auditoría total.
- **Autenticación JWT RS256** con refresh rotativo, revocación en Redis y
  rate-limiting con *fail-closed* (sin Redis, auth responde 503).
- **UI moderna** en Next.js 14 (App Router, standalone): tema claro estilo Apple,
  sidebar colapsable, dashboard con métricas reales, login con validación.
- **Calidad enterprise**: `ruff`, `mypy --strict`, cobertura ≥ 90 %, migraciones
  Alembic verificadas con `alembic check`, CI en GitHub Actions
  (SQLite + PostgreSQL real).

---

## Arquitectura

```text
Reloj ZKTeco (TCP/ADMS) ──▶ FastAPI :8000 (/iclock/*)
                                │  ├─ PostgreSQL :5432 (datos + auditoría)
Navegador ──▶ Next.js :3000 ──▶ │  └─ Redis :6379 (sesiones, rate-limit)
             (NEXT_PUBLIC_API_URL=http://localhost:8000)
```

| Servicio     | Puerto | Descripción                              |
| ------------ | ------ | ---------------------------------------- |
| `backend`    | 8000   | FastAPI: ADMS + API admin + `/health`    |
| `frontend`   | 3000   | Next.js standalone (`node server.js`)    |
| `postgres`   | 5432   | PostgreSQL 16 (`zkteco_adms`)            |
| `redis`      | 6379   | Redis 7 (auth, revocación, rate-limit)   |

---

## Requisitos

| Requisito | Versión mínima | Linux | Windows |
| --------- | -------------- | ----- | ------- |
| Python    | 3.12+          | `python3` (paquete `python3-venv`) | Python 3.12 de `python.org` (marcar *Add to PATH*) |
| Node.js   | 24 (LTS)       | `nodejs.org` o gestor (`nvm`, `fnm`) | Instalador LTS de `nodejs.org` |
| Docker    | 24+ con plugin Compose | Docker Engine + `docker compose` | **Docker Desktop** (con WSL2) |
| Git       | 2.x            | gestor de paquetes | Git for Windows (`autocrlf=true`) |

> En Windows usa **PowerShell** para todos los comandos de esta guía.

---

## Puesta en marcha: ¿Docker o manual?

| | **Opción A — Todo con Docker** (recomendada) | **Opción B — Híbrida** (desarrollo) |
|---|---|---|
| Infra (PG + Redis) | Contenedores | Contenedores |
| Backend | Contenedor (`adms-backend-1`) | Local (venv + uvicorn) |
| Frontend | Contenedor (`adms-frontend-1`) | Local (`npm run dev`) o contenedor |
| Ideal para | Probar el sistema tal cual | Modificar código con recarga |

### Opción A — Todo con Docker (Linux y Windows)

**1. Clonar:**

```bash
git clone git@github.com:jesmar81/adms.git
cd adms
```

**2. Crear `backend/.env` y las claves JWT** (ver
[`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)):

Linux:

```bash
cp backend/.env.example backend/.env
pip install cryptography
python3 - <<'EOF'
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
open('backend/.jwt_private.pem','wb').write(k.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption()))
open('backend/.jwt_public.pem','wb').write(k.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
EOF
```

Windows (PowerShell):

```powershell
Copy-Item backend\.env.example backend\.env
pip install cryptography
py -c "from cryptography.hazmat.primitives.asymmetric import rsa; from cryptography.hazmat.primitives import serialization; k = rsa.generate_private_key(public_exponent=65537, key_size=2048); open('backend/.jwt_private.pem','wb').write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())); open('backend/.jwt_public.pem','wb').write(k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))"
```

> `.env` y `*.pem` están en `.gitignore`: nunca se suben al repositorio.

**3. Definir el admin inicial en `backend/.env`** (el seed lo crea solo):

```text
ZKTECO_ADMIN_USERNAME=admin
ZKTECO_ADMIN_EMAIL=admin@example.com
ZKTECO_ADMIN_PASSWORD=cambia-esto-ya-01   # mínimo 10 caracteres
```

**4. Levantar todo:**

```bash
docker compose up -d --build
docker compose ps   # los 4 servicios en Up/healthy
```

El contenedor `backend` aplica migraciones solo (`alembic upgrade head`), monta
las claves JWT en solo-lectura y expone `:8000`. La UI queda en
`http://localhost:3000`.

**5. Crear datos base y admin (una sola vez):**

```bash
docker compose exec backend python -m app.seed
# o interactivo:
docker compose exec backend python -m app.cli createsuperuser
```

Verifica: `http://localhost:8000/health` → `{"status":"ok"}` e inicia sesión en
la UI.

### Opción B — Desarrollo local (híbrido)

Docker solo para PostgreSQL/Redis; backend y frontend corren en tu máquina con
recarga. Elige tu sistema:

---

## Instalación en Linux (paso a paso)

> Opción B (híbrida): la infraestructura va en Docker y el código corre local.
> Para todo-Docker, usa la [Opción A](#opción-a--todo-con-docker-linux-y-windows).

### 1. Clonar y entrar al proyecto

```bash
git clone git@github.com:jesmar81/adms.git
cd adms
```

### 2. Configurar variables de entorno y claves JWT

```bash
cp backend/.env.example backend/.env
pip install cryptography
python3 - <<'EOF'
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
open('backend/.jwt_private.pem','wb').write(k.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption()))
open('backend/.jwt_public.pem','wb').write(k.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
EOF
```

> `.env` y `*.pem` están en `.gitignore`: nunca se suben al repositorio.

### 3. Levantar infraestructura (PostgreSQL + Redis)

```bash
docker compose up -d postgres redis
docker compose ps   # ambos deben estar "healthy"
```

### 4. Backend: entorno virtual, migraciones y admin inicial

```bash
python3 -m venv env
source env/bin/activate
pip install -e "./backend[dev]"
cd backend
alembic upgrade head && alembic check
python -m app.seed
python -m app.cli createsuperuser   # crea el superusuario inicial (auditado)
```

Alternativa no interactiva (CI/desarrollo), con las mismas validaciones:

```bash
ZKTECO_ADMIN_USERNAME=admin ZKTECO_ADMIN_EMAIL=admin@example.com \
ZKTECO_ADMIN_PASSWORD='cambia-esto-ya-01' \
  python -m app.cli createsuperuser --no-input
```

### 5. Arrancar el backend

```bash
uvicorn app.main:app --reload --port 8000
# Salud:  curl http://localhost:8000/health   -> {"status":"ok"}
```

### 6. Frontend (en otra terminal)

```bash
cd frontend
npm ci
npm run lint && npm run typecheck && npm run build
npm run dev   # http://localhost:3000
```

> Para producción local con Docker (usa el Node 24 de la imagen):
> `docker compose up -d --no-deps --build frontend`

---

## Instalación en Windows (paso a paso)

> Opción B (híbrida): la infraestructura va en Docker y el código corre local.
> Para todo-Docker, usa la [Opción A](#opción-a--todo-con-docker-linux-y-windows).

> Requiere Docker Desktop en ejecución y Python/Node agregados al `PATH`.
> Verifica con `py --version`, `node --version`, `docker --version`.

### 1. Clonar y entrar al proyecto

```powershell
git clone git@github.com:jesmar81/adms.git
cd adms
```

### 2. Configurar variables de entorno y claves JWT

```powershell
Copy-Item backend\.env.example backend\.env
pip install cryptography
py -c "from cryptography.hazmat.primitives.asymmetric import rsa; from cryptography.hazmat.primitives import serialization; k = rsa.generate_private_key(public_exponent=65537, key_size=2048); open('backend/.jwt_private.pem','wb').write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())); open('backend/.jwt_public.pem','wb').write(k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))"
```

### 3. Levantar infraestructura (PostgreSQL + Redis)

```powershell
docker compose up -d postgres redis
docker compose ps   # ambos deben estar "healthy"
```

### 4. Backend: entorno virtual, migraciones y admin inicial

```powershell
py -m venv env
.\env\Scripts\Activate.ps1
pip install -e "./backend[dev]"
cd backend
alembic upgrade head
alembic check
python -m app.seed
python -m app.cli createsuperuser
```

> Si PowerShell bloquea la activación, ejecuta una vez (como tu usuario):
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 5. Arrancar el backend

```powershell
uvicorn app.main:app --reload --port 8000
# Salud:  curl http://localhost:8000/health   -> {"status":"ok"}
```

### 6. Frontend (en otra terminal PowerShell)

```powershell
cd frontend
npm ci
npm run lint
npm run typecheck
npm run build
npm run dev   # http://localhost:3000
```

> Para producción local con Docker:
> `docker compose up -d --no-deps --build frontend`

---

## Configuración

Variables principales en `backend/.env` (ver `backend/.env.example` comentado):

| Variable | Defecto | Descripción |
| -------- | ------- | ----------- |
| `DATABASE_URL` | `postgresql+asyncpg://zkteco:zkteco@localhost:5432/zkteco_adms` | Conexión PostgreSQL. En local usa `localhost`; el contenedor `backend` la sobrescribe a host `postgres` (ver `docker-compose.yml`) |
| `REDIS_URL` | `redis://localhost:6379/0` | Igual: en contenedor se sobrescribe a host `redis` |
| `JWT_PRIVATE_KEY_FILE` / `JWT_PUBLIC_KEY_FILE` | `.jwt_private.pem` / `.jwt_public.pem` | Claves RS256 (rotan con reinicio). El compose las monta en solo-lectura dentro del contenedor |
| `ZKTECO_ADMIN_USERNAME/EMAIL/PASSWORD` | — | Bootstrap del primer superusuario (mín. 10 caracteres) |
| `FRONTEND_ORIGINS_RAW` | — | **Obligatorio para la UI**: `http://localhost:3000` en local (el compose ya lo fija para el contenedor). Nunca `*` con credenciales |
| `RATELIMIT_*` | ver ejemplo | Límites de login/refresh/ADMS (Redis) |
| `ZKTECO_ONLINE_THRESHOLD` / `ZKTECO_STALE_AFTER` | `120` / `86400` | Ventanas de estado online/offline/stale (segundos) |
| `DOCS_ENABLED` | `true` | Expone `/docs` y `/openapi.json` (solo `/api/v1/*`) |

El frontend usa `NEXT_PUBLIC_API_URL` (defecto: `http://localhost:8000`).

---

## Uso

1. Abre `http://localhost:3000/login` e inicia sesión con el superusuario creado.
2. **Panel**: relojes en línea/fuera de línea, actividad reciente y comandos pendientes.
3. **Relojes**: apunta el SpeedFace-V5LP (servidor Push/ADMS) a `http://<tu-host>:8000`.
   El reloj se auto-registra vía `/iclock/registry`; el botón *Agregar reloj* explica
   el proceso (no existe alta manual: el backend no la contempla por diseño).
4. **Marcaciones / Personal / Comandos / Usuarios / Auditoría**: operan sobre datos
   reales de la API, con permisos por rol (`Can` en UI, enforcement en backend).

> Estado de validación con hardware real: **NO VERIFICADO** (sin dispositivo
> disponible). Ver `docs/DEVELOPMENT.md §5`.

---

## API

Superficie admin (requiere `Authorization: Bearer <access>`; errores en envelope
`{"error": {"code", "message", "request_id"}}`):

| Método | Ruta | Permiso |
| ------ | ---- | ------- |
| POST | `/api/v1/auth/login` · `/api/v1/auth/refresh` · `/api/v1/auth/logout` | público / sesión |
| GET | `/api/v1/auth/me` | sesión |
| GET | `/api/v1/devices` · `/api/v1/devices/{id}` · `/api/v1/devices/stats/summary` | `devices.read` |
| PATCH | `/api/v1/devices/{id}` · `/api/v1/devices/{id}/disable` | `devices.write` |
| GET | `/api/v1/attendance` | `attendance.read` |
| GET/POST/PUT/DELETE | `/api/v1/device-users…` | `device_users.*` |
| GET/POST | `/api/v1/devices/{id}/commands` · `/api/v1/commands` | `commands.*` |
| GET/POST/PATCH/DELETE | `/api/v1/users…` | `users.*` |
| GET | `/api/v1/audit` | `audit.read` |

Protocolo de relojes (sin JWT, `text/plain`): documentado en
[`docs/ADMS_PROTOCOL.md`](docs/ADMS_PROTOCOL.md).

---

## Testing

```bash
cd backend
# Unitarios (SQLite + Redis simulado, sin infra):
../env/bin/python -m pytest tests/unit        # Windows: ..\env\Scripts\python -m pytest tests/unit

# Integración contra PostgreSQL + Redis reales:
ZKTECO_TEST_PG_URL="postgresql+asyncpg://zkteco:zkteco@localhost:5432/zkteco_adms" \
ZKTECO_USE_REAL_REDIS=1 \
  pytest --cov=app --cov-report=term-missing --cov-fail-under=90
```

> ⚠️ Las fixtures de PG hacen `TRUNCATE`: usa una **base de datos de pruebas
> dedicada** (`zkteco_test`), nunca la de desarrollo.

```bash
cd frontend
npm run lint && npm run typecheck && npm run build
```

---

## Puertas de calidad

```bash
cd backend
ruff check app tests alembic && ruff format --check app tests alembic && mypy --strict app
alembic upgrade head && alembic check
```

El CI (`.github/workflows/ci.yml`) ejecuta en cada push/PR: backend con SQLite,
backend con PostgreSQL+Redis reales (cobertura ≥ 90 %) y frontend
(`lint` + `typecheck` + `build` en Node 24).

---

## Estructura del proyecto

```text
.
├── backend/            # FastAPI: app/, alembic/, tests/, pyproject.toml
│   ├── app/adms/       # Protocolo ADMS (parsers, router /iclock, comandos)
│   ├── app/api/v1/     # API admin (auth, devices, attendance, users…)
│   ├── app/core/       # config, seguridad JWT, DB, Redis, rate-limit
│   ├── app/models/     # SQLAlchemy (devices, users, tipos INET/UUID/JSONB)
│   └── app/services/   # bootstrap, device, command, audit…
├── frontend/           # Next.js 14 (App Router, standalone)
│   ├── app/(app)/      # Rutas protegidas + layout con sidebar
│   ├── components/     # Sistema de diseño + shell + ayudas
│   └── lib/            # api.ts (tokens en memoria), auth.tsx, format.ts
├── docs/               # Protocolo, DB, seguridad, testing, desarrollo
├── docker-compose.yml  # postgres, redis, backend, frontend
├── ARCHITECTURE.md     # Fuente de verdad del diseño
├── AUDIT_REPORT.md / REMEDIATION_REPORT.md
└── .github/workflows/ci.yml
```

---

## Seguridad

- JWT RS256 con `*_FILE`; rotación con reinicio; refresh revocable.
- Contraseñas Argon2id; el bootstrap por `.env` es solo para local
  (bórralo tras el primer seed; en producción usa el CLI interactivo).
- CORS con orígenes explícitos; `allow_origins=["*"]` prohibido con credenciales.
- Rate-limit y revocación exigidos por Redis (fail-closed).
- Detalle completo: [`docs/SECURITY.md`](docs/SECURITY.md).

---

## Solución de problemas

| Síntoma | Causa probable | Solución |
| ------- | -------------- | -------- |
| `No 'Access-Control-Allow-Origin'` en el navegador | Falta `FRONTEND_ORIGINS_RAW=http://localhost:3000` en `backend/.env` (sin él, el middleware CORS ni se instala) | Fíjalo y reinicia uvicorn |
| `401` en `/api/v1/devices` sin token | Esperado: requiere login | Inicia sesión; el frontend reintenta con refresh |
| `503` en login/refresh | Redis caído (auth es fail-closed) | `docker compose up -d redis` |
| Backend en Docker: login siempre `401` | Faltan las claves JWT en el host (el contenedor las monta) | Genera los `.pem` (paso 2) y `docker compose restart backend` |
| `alembic check` con diferencias | Migración pendiente o modelo sin migrar | `alembic upgrade head`; crea revisión si cambiaste modelos |
| Puerto 8000/3000 ocupado | Otro proceso | Libera el puerto o ajusta el mapeo en compose |
| En Windows, el reloj no alcanza `localhost:8000` | Firewall o `localhost` del dispositivo | Usa la IP LAN del host y permite el puerto en el firewall |
| Página sin estilos tras rebuild de Docker | Caché del navegador con hashes viejos | Recarga forzada (`Ctrl+Shift+R`) o ventana incógnita |

---

## Contribuir

1. Esquema solo vía migraciones (`alembic revision` + `upgrade head` + `check` limpio).
2. `seed`/`cli` nunca crean esquema.
3. Pasa las puertas de calidad (ruff, mypy strict, cobertura ≥ 90 %, `npm run lint/typecheck/build`).
4. Sin hardware, no declares validación con dispositivo real.

---

## Licencia

Este repositorio **no incluye aún un archivo de licencia**: por defecto, todos los
derechos quedan reservados a sus autores. Si el proyecto va a distribuirse o a
recibir contribuciones externas, se recomienda agregar una licencia explícita
(`LICENSE`, p. ej. MIT/Apache-2.0/AGPL) antes de publicar releases.
