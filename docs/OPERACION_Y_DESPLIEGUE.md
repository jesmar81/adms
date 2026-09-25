# Instalación y operación

Guía de despliegue y mantenimiento para desarrollo, pruebas internas y
operación. Para producción, adapta la red, gestión de secretos, TLS,
observabilidad y respaldos al entorno de la organización. Las credenciales
incluidas en Compose son valores locales de desarrollo, no secretos de
producción.

## 1. Componentes y requisitos

La solución contiene:

| Servicio | Función |
|---|---|
| Frontend Next.js | Interfaz web, normalmente puerto 3000. |
| Backend FastAPI | API administrativa, health checks y protocolo ADMS, normalmente puerto 8000. |
| PostgreSQL 16 | Datos transaccionales, marcas, relaciones y auditoría. |
| Redis 7 | Sesiones, revocación y control de frecuencia de autenticación. |
| Celery worker/beat opcional | Tareas de automatización, como mantener feriados legales. |

Para Compose se requiere Docker Engine/Desktop y Docker Compose. Para ejecutar
servicios localmente se requiere Python 3.12+, PostgreSQL 16+, Redis 7 y Node
24. Los servicios, volúmenes, puertos y variables se definen en
[`docker-compose.yml`](../docker-compose.yml) y
[`backend/.env.example`](../backend/.env.example).

## 2. Arranque con Docker Compose

Desde la raíz del repositorio:

```sh
cp backend/.env.example backend/.env
```

Genera un par RSA para JWT, manteniendo las claves fuera de Git:

```sh
python - <<'PY'
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
with open("backend/.jwt_private.pem", "wb") as f:
    f.write(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
with open("backend/.jwt_public.pem", "wb") as f:
    f.write(key.public_key().public_bytes(serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo))
PY
```

Revisa `backend/.env` y define `ZKTECO_ADMIN_USERNAME`,
`ZKTECO_ADMIN_EMAIL` y `ZKTECO_ADMIN_PASSWORD` solo para bootstrap local. La
contraseña requiere mínimo 15 caracteres. Un valor en `.env` está en texto
plano: quítalo después de la creación del administrador. En producción usa un
gestor de secretos y el CLI interactivo.

Levanta el stack y revisa sus estados:

```sh
docker compose up -d --build
docker compose ps
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
```

La interfaz queda en `http://localhost:3000`. El backend aplica las
migraciones pendientes al iniciar el contenedor. Crea los permisos/roles base
y el administrador inicial con:

```sh
docker compose exec backend python -m app.seed
```

El seed es idempotente y no sobrescribe una cuenta existente con el mismo
nombre. La alternativa para alta interactiva es:

```sh
docker compose exec backend python -m app.cli createsuperuser
```

No publiques los puertos de base de datos o Redis a redes no confiables. Los
puertos locales definidos por Compose son convenientes para desarrollo; en
producción usa redes privadas y reglas explícitas.

## 3. Configuración

Usa [`backend/.env.example`](../backend/.env.example) como inventario vigente.
Variables esenciales:

| Variable | Propósito |
|---|---|
| `DATABASE_URL` | URL async de PostgreSQL. En Compose el host es `postgres`. |
| `REDIS_URL` | Redis compartido para sesión y rate limiting. Auth falla de forma cerrada si no está disponible. |
| `JWT_PRIVATE_KEY_FILE`, `JWT_PUBLIC_KEY_FILE` | Rutas a claves RS256. La privada debe permanecer secreta. |
| `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_ACCESS_TTL`, `JWT_REFRESH_TTL` | Emisor, audiencia y vida de tokens. |
| `FRONTEND_ORIGINS_RAW` | Orígenes de navegador permitidos; configura el dominio exacto en despliegue. |
| `TRUSTED_PROXIES_RAW` | Redes de proxies confiables si se termina TLS delante de FastAPI. |
| `HSTS_ENABLED` | Activa HSTS cuando el proxy sirve HTTPS correctamente. |
| `DOCS_ENABLED` | Habilita/deshabilita OpenAPI `/docs`; ADMS no forma parte del esquema OpenAPI. |
| `ZKTECO_AUTO_REGISTER_UNKNOWN` | Debe permanecer `false` en operación normal. |
| `ZKTECO_HR_PII_ENCRYPTION_KEYS_RAW`, `ZKTECO_HR_PII_LOOKUP_KEY` | Cifrado y búsqueda de identificadores sensibles, si se habilitan. |

El API de autenticación necesita Redis disponible. Los archivos PEM, secretos
de cifrado, contraseñas y `backend/.env` no deben entrar al repositorio ni a
logs. Para detalles de controles, consulta [Seguridad](SECURITY.md).

## 4. Actualizar una instalación

1. Identifica y revisa la versión/cambios que se desplegarán.
2. Realiza un respaldo consistente de PostgreSQL y protege el archivo fuera
   del host de la aplicación.
3. Obtén el código autorizado para el despliegue y conserva una forma de
   regresar al artefacto anterior.
4. Reconstruye y levanta:

   ```sh
   docker compose up -d --build
   docker compose ps
   docker compose logs --tail=100 backend
   ```

5. Comprueba `/health`, `/ready`, login y las operaciones principales con una
   cuenta de prueba. Confirma también la conectividad de un reloj si aplica.

Las migraciones se ejecutan en el arranque del backend. No edites el esquema
directamente en producción; usa las migraciones Alembic del proyecto. Consulta
`alembic current`/historial con el equipo responsable antes de revertir un
cambio de esquema.

## 5. Copias de seguridad y recuperación

Respalda PostgreSQL de forma periódica con las herramientas de PostgreSQL o el
mecanismo gestionado del entorno. Ejemplo de exportación lógica desde un
contenedor Compose:

```sh
docker compose exec -T postgres pg_dump -U zkteco -d zkteco_adms -Fc > adms.dump
```

La contraseña de ejemplo anterior corresponde al Compose de desarrollo; usa
la identidad real del despliegue. Protege el dump porque puede contener datos
personales y de asistencia. Cifra el respaldo, limita acceso y define retención
conforme a las políticas aplicables.

La recuperación debe probarse periódicamente en una instancia aislada. Restaura
el archivo con `pg_restore` sobre una base vacía compatible y valida migración,
login, personas, empleos, marcaciones y auditoría antes de dirigir tráfico.
Respalda también de forma segura las claves JWT y claves de cifrado de datos
sensibles: perder una clave de cifrado puede impedir recuperar esos valores.
Mantén claves y dumps separados del repositorio y de los logs. El volumen Redis
no sustituye al respaldo de PostgreSQL; las sesiones se pueden invalidar al
perder Redis.

## 6. Alta y conexión de un reloj

1. Asigna al reloj una IP/DNS, ruta y puerto que alcancen el backend.
2. Registra su serial desde **Relojes** en la interfaz, asigna sucursal y zona
   horaria. El servidor rechaza seriales desconocidos por defecto.
3. En el menú de comunicación ADMS/Push del terminal, configura como servidor
   la URL y puerto publicados por el backend. Para un reloj físico no uses
   `localhost`; usa la dirección accesible desde su propia red.
4. Permite tráfico entrante hacia FastAPI únicamente desde las redes necesarias
   y establece conectividad privada (por ejemplo VPN) cuando el reloj esté
   fuera de una red controlada.
5. Revisa logs del backend y la actividad del reloj en la interfaz. Confirma
   que se actualice su última actividad y que los eventos de prueba lleguen.
6. Prueba recepción, reportes y cualquier comando en un entorno controlado
   antes de uso operativo.

El protocolo ADMS del fabricante no aporta identidad criptográfica suficiente
para confiar solo en el serial; aísla la red mediante VPN/firewall y restringe
el acceso. No actives `ZKTECO_AUTO_REGISTER_UNKNOWN` para resolver una conexión
en producción. Para compatibilidad por modelo y firmware, revisa
[`ADMS_PROTOCOL.md`](ADMS_PROTOCOL.md) y los documentos de SpeedFace. Un flujo
de UI/API que termina correctamente no prueba que el hardware haya ejecutado
la acción.

## 7. Tareas opcionales de RR. HH.

El perfil Compose `hr-automation` contiene Celery worker y beat. Si la
automatización de feriados es necesaria, configura el perfil correspondiente y
verifica que ambos procesos permanezcan activos:

```sh
docker compose --profile hr-automation up -d
docker compose --profile hr-automation ps
```

Si no se despliega beat, la reparación/generación de feriados puede ejecutarse
manualmente desde la pantalla **Feriados**. Confirma los feriados aplicables
por empresa y año aunque la automatización esté habilitada.

## 8. Observabilidad y solución de problemas

Comandos útiles:

```sh
docker compose ps
docker compose logs --tail=100 backend
docker compose logs --tail=100 frontend
docker compose logs --tail=100 postgres
docker compose logs --tail=100 redis
```

| Síntoma | Causa probable y acción |
|---|---|
| `/health` no responde | Revisa que backend esté arriba y puerto 8000 accesible; consulta logs. |
| `/health` está bien, pero `/ready` falla | Comprueba conectividad con PostgreSQL y Redis y sus credenciales/URLs. |
| Login devuelve indisponibilidad | Redis es dependencia obligatoria para sesión y limitación de acceso; restablece Redis antes de reintentar. |
| Frontend no conecta al API | Comprueba `NEXT_PUBLIC_API_URL`, CORS y que el navegador pueda alcanzar esa URL. Reconstruye el frontend si cambió una variable `NEXT_PUBLIC_*`. |
| Backend reinicia al arrancar | Revisa migración, URL de base, archivos de clave, permisos de lectura y logs. |
| El reloj no conecta | Comprueba URL ADMS, DNS/IP desde la red del reloj, reglas/firewall, serial autorizado y logs de backend. |
| No hay marcas nuevas | Verifica tráfico ADMS, actividad del terminal, formato/tabla de envío y filtros de la interfaz. |
| Reportes difieren de lo esperado | Comprueba horario efectivo, empleo activo, zona horaria, días de descanso y feriados. |
| Comando no se completa | Revisa conectividad, perfil del terminal, expiración e intentos. Un estado en cola no garantiza ejecución. |

Al reportar un incidente incluye fecha/hora con zona, entorno, serial (si
aplica), endpoint/acción, request ID y mensajes sanitizados. Nunca incluyas
contraseñas, tokens, claves privadas ni datos biométricos.

## 9. Notas de seguridad de operación

- Termina TLS en un proxy confiable y configura orígenes CORS explícitos.
- Mantén Redis y PostgreSQL en redes privadas. Evita publicar sus puertos a
  Internet.
- Cambia todos los valores de ejemplo y limita las cuentas administrativas.
- Almacena claves en un gestor de secretos; rota claves con un procedimiento
  que preserve acceso a datos cifrados.
- Aplica actualizaciones del sistema operativo, runtime, imágenes y dependencias
  según el proceso de cambios de la organización.
- Conserva logs y respaldos con controles de acceso y retención definidos.
- Consulta [`SECURITY.md`](SECURITY.md) para el detalle de la autenticación,
  RBAC, datos sensibles, límites ADMS y auditoría.
