# Testing

La suite completa se ejecuta exclusivamente con PostgreSQL y Redis reales, sin
sustitutos en memoria para persistencia o servicios. PostgreSQL se migra con
Alembic antes de correr los casos y cada prueba limpia sus tablas en una base
dedicada. Redis usa y limpia la base lógica 15.

## Preparar servicios

Levanta PostgreSQL y Redis desde la raíz del proyecto:

```bash
docker compose up -d postgres redis
```

En una instalación nueva crea una vez la base dedicada de tests:

```bash
docker compose exec postgres createdb -U zkteco adms_integration_tests
```

Omite ese comando si la base ya existe.

Usa una base cuyo nombre incluya `test`; la suite vacía sus tablas. No apuntes
`ZKTECO_TEST_PG_URL` a una base de desarrollo o producción.

```bash
cd backend
export ZKTECO_TEST_PG_URL="postgresql+asyncpg://zkteco:zkteco@localhost:5432/adms_integration_tests"
export ZKTECO_TEST_REDIS_URL="redis://localhost:6379/15"
export DATABASE_URL="$ZKTECO_TEST_PG_URL"
export REDIS_URL="$ZKTECO_TEST_REDIS_URL"
```

La base PostgreSQL debe existir y aceptar conexiones para el usuario indicado.
La suite crea una base temporal sin migrar para comprobar que el CLI rechace
esquemas vacíos, y la elimina al terminar ese caso.

## Comandos

```bash
cd backend
pip install -e '.[dev]'
alembic upgrade head
alembic check
pytest tests --cov=app --cov-report=term-missing --cov-fail-under=60
ruff check app tests alembic
ruff format --check app tests alembic
mypy --strict app
```

CI ejecuta estos chequeos de backend y la suite completa contra PostgreSQL 16 y
Redis 7 en cada push y pull request. La cobertura actual medida es 63.5%; el
gate queda en 60% mientras se amplían las pruebas de los módulos HR/reportes.
Las pruebas marcadas `pg` cubren tipos
nativos, restricciones, índices y concurrencia de PostgreSQL; el resto de la
suite también usa PostgreSQL y Redis reales.

## Cobertura

- Protocolo ADMS: registro, ATTLOG, RTLOG, USERINFO, OPERLOG y confirmaciones.
- Persistencia e idempotencia: duplicados, atribuciones, fallos transaccionales
  y reintentos comprobados mediante restricciones y triggers PostgreSQL reales.
- Concurrencia: límites de registro, colas y `SKIP LOCKED` sobre PostgreSQL.
- Redis compartido: rate limiting, revocación y políticas ante desconexión
  verificadas con clientes independientes del servicio real.
- Seguridad: autenticación, revocación, RBAC, respuestas de error y límites.

No uses `create_all` como reemplazo de migraciones en pruebas. Los servicios y
la API trabajan sobre el esquema producido por Alembic.

## Preparación E2E del navegador

La estrategia pendiente para recorrer la UI, cubrir el enrolamiento y aislar
los datos está en [`E2E_TEST_PREPARATION.md`](E2E_TEST_PREPARATION.md). La suite
de navegador todavía no está configurada.
