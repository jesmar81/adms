# Documentación de ZKTeco ADMS

Documentación en español de la plataforma de asistencia y administración de
relojes ZKTeco. Actualizada el **25 de septiembre de 2026**. La guía describe
la interfaz y el comportamiento disponible en el código de esta versión; las
capacidades que dependen de firmware o de hardware se indican expresamente.

## Empezar

- **[Guía de uso](GUIA_USUARIO.md)**: acceso, configuración inicial y operación
  diaria de cada módulo de la interfaz.
- **[Instalación y operación](OPERACION_Y_DESPLIEGUE.md)**: requisitos, Docker,
  variables, alta de administradores y relojes, mantenimiento y resolución de
  incidentes.

## Referencias técnicas

- [Desarrollo local](DEVELOPMENT.md): entorno de desarrollo, tareas de calidad
  y pruebas.
- [Seguridad](SECURITY.md): autenticación, permisos, alcance de datos,
  secretos, privacidad y límites del protocolo del reloj.
- [Protocolo ADMS](ADMS_PROTOCOL.md): endpoints, recepción de datos y ciclo de
  comandos.
- [Captura de comandos de usuario SpeedFace](SPEEDFACE_V5L_USER_COMMAND_CAPTURE.md)
  y [despliegue SpeedFace](SPEEDFACE_V5L_ENTERPRISE_ROLLOUT.md): evidencia,
  compatibilidad observada y validación pendiente con equipo físico.
- [Base de datos](DATABASE.md): esquema y persistencia.
- [Calendario laboral de México](HR_CALENDARS_MX.md): feriados y protección de
  identificadores laborales.
- [Modelo de personal y asistencia](HR_ATTENDANCE_DOMAIN_PLAN.md): contexto
  del dominio y diseño; puede contener propuestas que aún no forman parte de
  la aplicación.
- [Pruebas](TESTING.md): organización y ejecución de pruebas.

## Mapa de documentos

| Necesito… | Consultar |
|---|---|
| Aprender el trabajo diario en la interfaz | [Guía de uso](GUIA_USUARIO.md) |
| Instalar la aplicación o actualizar una instancia | [Instalación y operación](OPERACION_Y_DESPLIEGUE.md) |
| Dar de alta un reloj y conectarlo por ADMS | [Operación](OPERACION_Y_DESPLIEGUE.md#alta-y-conexion-de-un-reloj) y [protocolo](ADMS_PROTOCOL.md) |
| Asignar accesos a un usuario | [Guía de uso: usuarios](GUIA_USUARIO.md#usuarios-y-permisos) |
| Diagnosticar asistencia o reportes | [Guía de uso: asistencia](GUIA_USUARIO.md#asistencia-y-reportes) |
| Revisar seguridad y datos personales | [Seguridad](SECURITY.md) |
| Desarrollar o probar cambios | [Desarrollo](DEVELOPMENT.md) y [pruebas](TESTING.md) |

## Alcance y terminología

La plataforma tiene una interfaz web, una API administrativa autenticada y
endpoints ADMS que reciben la comunicación iniciada por el reloj. En esta
documentación, **reloj** o **terminal** significa el equipo físico; **usuario
del sistema** es quien inicia sesión en la aplicación; y **usuario del reloj**
es el registro de PIN/nombre que existe en un terminal. Una persona puede
tener uno o más empleos; el empleo conecta a la persona con una empresa y da
contexto a horarios y asistencia.

La interfaz puede simular y administrar flujos sin hardware. La recepción real
de marcas, enrolamiento biométrico en terminal y ejecución de comandos requiere
conectividad y compatibilidad comprobada del modelo/firmware. Consulta las
referencias SpeedFace antes de asumir que una operación de laboratorio está
validada para producción.
