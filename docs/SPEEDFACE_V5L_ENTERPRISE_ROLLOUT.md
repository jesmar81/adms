# Despliegue enterprise del SpeedFace-V5L (A&C PUSH)

## Estado basado en evidencia

Las capturas reales del 15 y 17 de septiembre confirman el perfil **A&C PUSH /
Security PUSH** y estas operaciones:

- `GET /iclock/getrequest` (sondeo del reloj);
- `POST /iclock/cdata?table=rtstate`;
- `POST /iclock/cdata?table=rtlog` con PIN, hora, estado y método de
  verificación;
- entrega del comando de sólo lectura `INFO` mediante `getrequest`.

No confirma todavía `querydata`, el formato de consulta de usuarios, ni el
significado de `Return=-5000`. Por ello el sistema recibe y audita
`/iclock/querydata`, pero bloquea las escrituras de usuarios hechas con el
wire legacy `DATA ... USERINFO` cuando el dispositivo se identifica como
`DeviceType=acc`.

Esta barrera es intencional: una cola marcada como exitosa sin evidencia de
que el equipo aplicó el cambio no es una integración apta para producción.

## Controles no negociables

1. Mantener el V5L en el tipo de dispositivo que ya opera. Cambiar entre
   A&C PUSH y T&A PUSH puede borrar datos y reiniciar el equipo; no se cambia
   para probar la integración.
2. El reloj conserva las plantillas biométricas. La plataforma sólo registra
   solicitud, operador, método y resultado de verificación; si llega
   `querydata` biométrico, se conserva únicamente su hash y evidencia de que
   fue rechazado, nunca el cuerpo.
3. Cada PIN debe vincularse a una persona y el reloj a un sitio/empresa antes
   de usar la asistencia para una decisión laboral.
4. Nunca declarar una sincronización terminada por el envío del comando. Sólo
   se completa tras una confirmación inequívoca del V5L o una importación de
   retorno que muestre el usuario esperado.

## Siguiente captura controlada

La validación integral anterior ya está archivada. En una ventana de
mantenimiento, con un operador y exclusivamente un PIN de laboratorio, sigue
la [captura activa de comandos](SPEEDFACE_V5L_USER_COMMAND_CAPTURE.md). El
asistente registra consulta, alta, cambio de nombre y baja contra el reloj,
junto con sus respuestas reales, sin tocar por sí mismo el dispositivo.

El PCAP y las transcripciones contienen datos personales: se conservan fuera
de Git y se revisan antes de usar estas operaciones en producción.

## Criterios para habilitar sincronización

Para cada versión de firmware se conserva un caso de prueba que demuestre:

- comando emitido, respuesta HTTP y `devicecmd` correlacionados por ID;
- resultado de `querydata` con usuario normalizado y sin biometría;
- semántica comprobada de códigos negativos, incluido `-5000` si aparece;
- reintento idempotente sin duplicar usuarios ni comandos;
- prueba de alta, modificación, baja y revocación sobre identidades de
  laboratorio.

El formato de usuario y la semántica de `Return=-5000` no se infieren de
ejemplos de otros firmwares.
