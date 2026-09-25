# Preparación de pruebas E2E

## Propósito

Este documento prepara una futura suite de pruebas de extremo a extremo (E2E)
para la aplicación web, empezando por el flujo de enrolamiento de trabajadores.
La suite comprobará el recorrido desde el navegador hasta la API y la
persistencia en PostgreSQL. **Las pruebas todavía no están configuradas ni se
deben ejecutar como parte de esta preparación.**

## Estado actual

- El backend ya tiene pruebas unitarias y de integración; su configuración y
  sus requisitos están en [`TESTING.md`](TESTING.md).
- El frontend no tiene configuración ni scripts E2E de Playwright o Cypress.
- El Compose habitual usa volúmenes persistentes. No debe usarse para pruebas
  que creen, limpien o reemplacen datos de forma automática.
- El sistema registra a la **persona trabajadora**. Su empleo y empresa aportan
  el contexto laboral del enrolamiento; no son la identidad que se enrola.

## Enfoque propuesto

Usar Playwright para recorrer la interfaz real en un navegador y una instancia
E2E aislada de Docker Compose. La configuración futura debe separar frontend,
backend, PostgreSQL y Redis de los servicios de desarrollo, con volúmenes y
credenciales exclusivos. Los puertos publicados también deben evitar
conflictos con el Compose de desarrollo.

La base E2E debe crearse con un nombre que la identifique claramente como
descartable, aplicar las migraciones Alembic y usar datos de prueba
deterministas. Un mecanismo de protección debe impedir que la preparación o
limpieza opere sobre la base de desarrollo o producción. Redis debe estar
aislado de las sesiones y límites de tasa usados por otros entornos.

La suite debe probar la UI y comprobar las respuestas de la API. Cuando el caso
valide persistencia, verificará el resultado por el historial de la aplicación
o por una consulta de solo lectura contra la base E2E. No debe guardar ni
transmitir plantillas biométricas reales.

## Datos de prueba previstos

Preparar fixtures repetibles con:

- Una cuenta con permisos para crear y leer solicitudes de enrolamiento.
- Una cuenta con permiso de aprobación y distinta de quien crea la solicitud.
- Una cuenta sin permiso de escritura de enrolamientos.
- Dos empresas, cada una con sitio y reloj activo.
- Una persona trabajadora con empleo activo y vigente en la primera empresa.
- Personas con empleo inactivo, futuro o vencido para cubrir inelegibilidad.
- Una persona con contexto laboral en otra empresa para comprobar el alcance.
- Opcionalmente, una persona con más de un empleo vigente para comprobar que
  reloj, empresa y contexto laboral permanecen asociados correctamente.

Los nombres y números de empleado deben ser ficticios y estables entre
ejecuciones. El proceso de preparación debe poder recrear los fixtures sin
tocar ninguna base que no sea la E2E.

## Escenarios priorizados

### P0 — Entrada y acceso

1. Abrir la aplicación sin sesión y comprobar que conduce al inicio de sesión.
2. Iniciar sesión con la cuenta E2E y llegar a la pantalla de enrolamientos.
3. Confirmar que una cuenta sin `enrollments.write` no puede crear solicitudes
   ni desde la interfaz ni llamando directamente a la API.
4. Confirmar que un usuario con permiso de lectura puede consultar el historial
   sin que aparezcan controles de creación o aprobación que no le corresponden.

### P1 — Selección y registro de la persona trabajadora

1. Elegir primero un reloj activo y después cargar candidatos elegibles para
   el contexto de ese reloj.
2. Buscar por nombre y número de empleado, seleccionar a la persona correcta y
   confirmar visualmente su nombre, empresa y sitio cuando estén disponibles.
3. Seleccionar el método de enrolamiento. Si incluye huella, elegir al menos
   una posición.
4. Crear la solicitud y comprobar que se conserva la persona, el contexto de
   empleo, el reloj, los métodos y las posiciones.
5. Recargar la página y comprobar que el historial presenta el nombre y los
   datos laborales legibles de la persona, no un UUID como identidad visible.

### P1 — Elegibilidad y límites entre empresas

- El reloj de la empresa A presenta únicamente personas elegibles para ese
  contexto y alcance de usuario.
- Cambiar de reloj actualiza los candidatos y elimina una selección que ya no
  pertenece al nuevo contexto.
- Empleos inactivos, futuros o vencidos no se ofrecen para el enrolamiento.
- La API rechaza un empleo y una persona que no corresponden, un reloj de otra
  empresa y una persona fuera del alcance del usuario.
- Una lista sin candidatos muestra un estado vacío entendible y no permite
  enviar una solicitud incompleta.

### P2 — Validaciones, errores y concurrencia de UI

- No se puede enviar sin reloj, persona, método o datos requeridos.
- La API rechaza posiciones de huella duplicadas o no soportadas y posiciones
  sin método de huella.
- Fallos al cargar relojes, historial o candidatos muestran errores claros y
  permiten reintentar.
- Una respuesta tardía de una búsqueda anterior no reemplaza los candidatos de
  la selección de reloj más reciente.
- Doble clic, respuesta lenta o fallo de red no deben crear solicitudes
  duplicadas ni borrar silenciosamente una selección válida.

### P2 — Aprobación e historial

Con la cuenta de RR. HH., recorrer la secuencia soportada por la aplicación:

`requested → identity_verified → approved → awaiting_device_enrollment → verification_pending → completed`

También comprobar rechazo y revocación cuando estén permitidos. La misma
cuenta de RR. HH. puede crear, verificar y aprobar una solicitud. Las
transiciones inválidas deben ser rechazadas por la API y dejar el estado
anterior intacto en el historial.

La comunicación con un reloj físico queda fuera de la suite E2E de navegador.
En el entorno E2E se validará el registro de la solicitud y sus estados; una
prueba con hardware real se planificará por separado.

## Evidencia al fallar

Playwright debe guardar en fallos:

- Captura de pantalla y traza de navegador.
- Errores de consola y solicitudes de red con método, ruta y código HTTP.
- Logs del backend y del frontend para la ventana de la prueba.
- Identificador de la solicitud E2E y datos mínimos para reproducir el caso.

Los artefactos deben excluir contraseñas, tokens, referencias personales reales
y cualquier plantilla biométrica.

## Preparación pendiente antes de ejecutar

- [ ] Elegir e instalar Playwright y añadir configuración y scripts del
      frontend.
- [ ] Definir el Compose E2E aislado, sus puertos, volúmenes y servicios.
- [ ] Implementar un bootstrap de fixtures E2E con protección explícita del
      nombre de base de datos.
- [ ] Definir cuentas ficticias y cómo se guardarán sus credenciales localmente
      y en CI.
- [ ] Acordar qué escenarios entrarán primero al pipeline de CI y la retención
      de artefactos.
- [ ] Documentar el comando de ejecución y limpieza una vez que lo anterior
      esté listo.

## Criterios para considerar lista la primera suite

- La preparación solo puede crear y limpiar recursos del entorno E2E.
- El escenario feliz crea una solicitud para la persona seleccionada y la
  muestra correctamente en el historial después de recargar.
- Los controles de empresa, elegibilidad y permisos son comprobados en el
  backend además de reflejarse en la UI.
- Los escenarios prioritarios dejan evidencia reproducible en caso de fallo.
- Las pruebas no usan hardware ni datos biométricos reales.
