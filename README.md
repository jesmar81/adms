# ZKTECO ADMS PLATFORM

Professional attendance-management platform for ZKTeco biometric devices
(priority: **SpeedFace-V5LP**) — FastAPI ADMS gateway + PostgreSQL + Redis +
Next.js admin UI.

Functional reference (protocol only, not a port):
`https://github.com/athwari/laravel-zkteco-adms-server`

- **Source of truth:** [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Audit: [`AUDIT_REPORT.md`](AUDIT_REPORT.md) (FAIL 66/100) →
  remediation: [`REMEDIATION_REPORT.md`](REMEDIATION_REPORT.md)
- Protocol spec: [`docs/ADMS_PROTOCOL.md`](docs/ADMS_PROTOCOL.md)
- Database: [`docs/DATABASE.md`](docs/DATABASE.md)
- Security: [`docs/SECURITY.md`](docs/SECURITY.md)
- Testing: [`docs/TESTING.md`](docs/TESTING.md)
- Development: [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)

## Quickstart

```bash
cp backend/.env.example backend/.env   # then generate RS256 keys (see docs/DEVELOPMENT.md)
docker compose up -d postgres redis
cd backend && pip install -e ".[dev]" && alembic upgrade head && alembic check
python -m app.seed && python -m app.cli createsuperuser
uvicorn app.main:app --reload
```

Point the SpeedFace-V5LP Push/ADMS server to `http://<host>:8000`.
Real-device validation status: **NOT VERIFIED** (no hardware available).

Frontend: `cd frontend && npm ci && npm run build`.

## Quality gates

```bash
cd backend
ruff check app tests alembic && ruff format --check app tests alembic && mypy --strict app
ZKTECO_TEST_PG_URL="postgresql+asyncpg://…" pytest --cov=app --cov-report=term-missing --cov-fail-under=90
alembic upgrade head && alembic check
```
