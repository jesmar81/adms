# Dominio corporativo: personal, horarios y asistencia

## Decisión de arquitectura

El sistema atenderá a un **grupo corporativo** que puede tener varias empresas
legales. La administración puede operar sobre todas las empresas, pero cada
empleo, turno, centro de costo y resultado de asistencia pertenece a una sola
empresa.

Una persona no se duplica si trabaja en dos empresas. Se crea una `person` en
el grupo y un `employment` por cada relación laboral. Una cuenta administrativa
es independiente de la persona, aunque opcionalmente puede estar vinculada a
ella; su acceso se delimita por empresas o por todo el grupo.

```text
corporate_group
├── company A ── site ── device
│   └── employment A ── schedule assignment A
├── company B ── site ── device
│   └── employment B ── schedule assignment B
└── person ── device identity (PIN/biometric enrollment on each device)
```

## Regla esencial para las checadas

El V5L entrega PIN, hora, evento, estado y método de verificación; no entrega
empresa. Una checada se asigna a un empleo por contexto, en este orden:

1. empresa del sitio/reloj;
2. `work_code` seleccionado en el reloj, si está configurado;
3. asignación explícita de puerta, dispositivo o área;
4. regla temporal solo cuando deja una única opción, marcada como inferida.

Nunca se usará únicamente la hora para elegir entre dos empleos traslapados.
Una checada ambigua queda en revisión en vez de afectar nómina de manera
silenciosa.

## Modelo de datos

### Estructura corporativa

- `corporate_groups`: grupo dueño de los datos.
- `companies`: razón social, nombre comercial, RFC, registro patronal IMSS,
  domicilio fiscal, zona horaria y estado.
- `sites`: centro de trabajo, empresa, dirección y zona horaria.
- `user_company_scopes`: empresas que un administrador puede consultar u
  operar. El rol `group_admin` tiene alcance a todo el grupo.

### Personas y empleo

- `people`: identidad compartida: nombres legales, apellidos, nombre preferido,
  correo y teléfonos de contacto.
- `person_sensitive_identifiers`: CURP, RFC y NSS/IMSS cifrados; hashes de
  búsqueda con llave para detección de duplicados. No usar JSON genérico para
  estos valores.
- `employments`: persona, empresa, número de empleado, puesto, departamento,
  centro de costo, jefe, tipo de contrato, fecha de alta/baja y estado.
- `device_identities`: relación de una persona con PIN/tarjeta de un reloj.
  Reemplaza gradualmente el significado de `device_users`; la tabla antigua se
  conserva durante la migración por compatibilidad con ADMS.

Información de nómina, CLABE, expediente médico, documentos de identidad e
imágenes quedan fuera de esta fase. Si llegan a ser necesarios, tendrán un
módulo de nómina/expediente separado, cifrado y con permisos más restrictivos.

### Horarios y reglas

- `work_schedules`: definición reutilizable y versionada, siempre con zona
  horaria.
- `schedule_days`: día de semana, descanso, festivo o jornada especial.
- `schedule_slots`: varios intervalos por día: `entry`, `meal_out`, `meal_in`,
  `exit`, guardia o intervalo partido. Cada slot define ventana aceptable,
  tolerancia y si es obligatorio.
- `meal_rules`: comida fija o flexible, duración mínima/máxima, ventana y si
  es pagada.
- `schedule_assignments`: empleo + horario + vigencia. Se prohíben traslapes
  ambiguos para un mismo empleo.
- `attendance_exceptions`: vacaciones, incapacidad, permiso, festivo local,
  cambio temporal de turno o incidencia aprobada.
- `attendance_evaluations`: resultado derivado y versionado de cada periodo:
  retardos, faltas, comida, salida temprana, horas trabajadas y extra.

`attendance_logs` conserva siempre el evento original del reloj. Las
evaluaciones se pueden recalcular cuando cambia una política sin modificar la
evidencia original.

### Enrolamiento biométrico

- `enrollment_requests`: empleo/persona, reloj, métodos solicitados, operador,
  aprobador, consentimiento/aviso aplicable, estado y evidencia de prueba.
- Estados: `requested`, `approved`, `identity_verified`,
  `awaiting_device_enrollment`, `verification_pending`, `completed`,
  `rejected`, `revoked`.
- El reloj realiza la captura facial/huella. La plataforma registra el flujo y
  la auditoría, pero no guarda plantillas, fotografías ni datos biométricos
  crudos.

## API administrativa

Todos los endpoints pertenecen a `/api/v1`; las respuestas se filtran por el
alcance de empresa del usuario autenticado.

| Recurso | Endpoints principales | Permiso |
| --- | --- | --- |
| Grupo y empresas | `GET/POST /corporate-groups`, `GET/PATCH /companies/{id}` | `companies.read/write` |
| Sitios | `GET/POST /sites`, `GET/PATCH /sites/{id}` | `sites.read/write` |
| Ámbitos de admin | `GET/PUT /users/{id}/company-scopes` | `users.write` |
| Personas | `GET/POST /people`, `GET/PATCH /people/{id}` | `people.read/write` |
| Identificadores sensibles | `GET/PATCH /people/{id}/sensitive-identifiers` | `people.sensitive.read/write` |
| Empleos | `GET /employments`, `POST /people/{id}/employments`, `PATCH /employments/{id}` | `employments.read/write` |
| Horarios | `GET/POST /work-schedules`, `GET/PATCH /work-schedules/{id}` | `schedules.read/write` |
| Asignación de horario | `POST /employments/{id}/schedule-assignments`, `PATCH /schedule-assignments/{id}` | `schedules.write` |
| Excepciones | `POST /employments/{id}/attendance-exceptions` | `attendance.write` |
| Enrolamiento | `GET/POST /enrollment-requests`, `PATCH /enrollment-requests/{id}` | `enrollments.read/write/approve` |
| Importar usuarios | `POST /devices/{id}/users/import` | `device_users.write` |
| Sincronizar usuario | `POST /device-identities/{id}/sync` | `device_users.write` |
| Asistencia cruda | `GET /attendance` con filtros `company_id`, `person_id`, `employment_id`, `site_id` | `attendance.read` |
| Asistencia evaluada | `GET /attendance-evaluations`, `POST /attendance-evaluations/recalculate` | `attendance.read/write` |

## Actualizaciones de endpoints existentes

- `GET/PATCH /devices/{id}` incluirá `site_id`; el sitio determina su empresa y
  zona horaria por defecto.
- `/device-users` seguirá funcionando durante la transición, pero expondrá
  `person_id` e identidad de reloj. No será el expediente laboral maestro.
- `GET /attendance` seguirá devolviendo registros crudos y añadirá filtros y
  referencias a empresa, persona, empleo y sitio cuando ya estén resueltas.
- Se agrega `/iclock/querydata` al protocolo ADMS para importar usuarios y
  transacciones desde el V5L. Los comandos de alta/baja se cambiarán al formato
  Security PUSH capturado del dispositivo, no al formato legacy actual.

## Seguridad y auditoría

- Cifrado de aplicación para CURP, RFC y NSS, con claves fuera de la base de
  datos y rotación documentada.
- Búsqueda de identificadores mediante HMAC normalizado, no texto plano.
- MFA para administradores, separación entre quien crea, aprueba y enrola.
- Auditoría inmutable de lectura de datos sensibles, cambios de empleo,
  horarios, enrolamientos, exportaciones y recálculos.
- Sin plantillas biométricas en la plataforma en esta fase. Se documentará
  aviso de privacidad, conservación y borrado antes de activar enrolamientos.

## Entregas y criterios de aceptación

1. **Fundación:** migraciones, empresas, sitios, personas, empleos y scopes;
   datos existentes siguen operando sin pérdida.
2. **Dispositivo:** `querydata`, perfil Security PUSH, importación de usuarios
   y vínculo de identidad a persona.
3. **Enrolamiento:** flujo supervisado, auditoría y prueba de verificación.
4. **Horario:** asignaciones efectivas, comida flexible/fija, excepciones y
   evaluaciones reproducibles.
5. **Operación:** reportes por empresa/persona, exportación con permisos y
   conciliación de checadas ambiguas.

No se habilita cálculo de nómina ni transferencia de biometría hasta que cada
fase tenga pruebas con el V5L real, políticas aprobadas y controles de acceso
verificados.
