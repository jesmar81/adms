# Despliegue enterprise del SpeedFace-V5L (A&C PUSH)

## Estado basado en evidencia

La captura real del 15 de septiembre confirma el perfil **A&C PUSH / Security
PUSH** y estas operaciones:

- `GET /iclock/getrequest` (sondeo del reloj);
- `POST /iclock/cdata?table=rtstate`;
- `POST /iclock/cdata?table=rtlog` con PIN, hora, estado y método de
  verificación.

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

En una ventana de mantenimiento, con sólo un operador y sin editar usuarios
productivos:

1. Capturar diez minutos con `scripts/capture_adms_session.ps1` en el servidor
   que recibe al reloj.
2. Desde el panel, emitir únicamente una consulta inocua (`INFO` o un GET de
   opción), esperar la siguiente llamada `getrequest` y guardar la respuesta
   completa del reloj, especialmente `devicecmd` y el valor `Return`.
3. Usar la función de consulta de usuarios del propio menú del equipo, si la
   tiene, sin dar de alta ni borrar nada. Se debe capturar cualquier llamada a
   `querydata`, incluidos `type`, `table`, `cmdid`, cuerpo y acuse HTTP.
4. Decodificar el PCAP localmente. El PCAP y las transcripciones contienen
   datos personales: se conservan fuera de Git.

Con esa evidencia se añade el adaptador de lectura de usuarios exacto. Sólo
después se prueba una alta sobre un PIN de laboratorio y se habilitan cambios
de producción mediante aprobación de dos personas.

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
