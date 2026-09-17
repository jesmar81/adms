# Captura pendiente: usuarios del SpeedFace-V5L

## Estado cerrado

Las capturas del 15 y 17 de septiembre de 2026 ya demostraron en este
firmware A&C / Security PUSH:

- sondeo `GET /iclock/getrequest`;
- estado `POST /iclock/cdata?table=rtstate`;
- checadas en tiempo real `POST /iclock/cdata?table=rtlog`;
- entrega y retorno del comando de sólo lectura `INFO`.

No deben repetirse esas pruebas. La captura del 17 de septiembre registró
cero llamadas a `querydata`, por lo que todavía no existe evidencia para
importar usuarios ni para escribirlos desde ADMS.

## Única captura a realizar ahora

Hace falta observar una **lectura de inventario de usuarios** producida por el
sistema autorizado que ya administra este reloj. Debe contener la petición,
respuesta, finalización/paginación y acuse del V5L. No se adivina un comando
ni se envía uno desde ADMS.

En el servidor Windows que recibe el reloj, instala Wireshark con Npcap y usa:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\capture_speedface_v5l_remaining.ps1 -DeviceIp 192.168.68.201 -ListInterfaces

.\scripts\capture_speedface_v5l_remaining.ps1 `
  -DeviceIp 192.168.68.201 `
  -Interface 1 `
  -ServerPort 8000 `
  -Phase UserRead
```

El asistente es pasivo. Cuando lo indique, usa en el sistema autorizado sólo
la función equivalente a “listar”, “consultar” o “descargar usuarios desde
dispositivo”. No ejecutes altas, modificaciones, bajas, cambio A&C/T&A PUSH,
reinicio ni operaciones de plantillas biométricas.

El resultado queda en `captures/pending/`:

- `*.pcapng`: evidencia cruda; autoritativa;
- `*.metadata.txt`: filtro, host, fase y SHA-256;
- `*.timeline.csv`: pasos manuales con hora UTC;
- `*.evidence-summary.json`: confirma si se observó transporte de usuario;
- `*.decoded/`: transcripciones sensibles, sólo para transferencia privada.

Si `user_transport_observed` es `false`, no se habilita ninguna escritura. La
consulta no se ejecutó desde el sistema correcto o el equipo no la soporta;
entrega esa evidencia privada antes de intentar otra acción.

## Después de validar la lectura

Sólo cuando la lectura exacta haya sido revisada, se podrá capturar el ciclo
completo sobre un PIN de laboratorio: alta, lectura, cambio de nombre visible,
lectura, baja y lectura final. El mismo asistente lo protege con una referencia
de aprobación y nunca manipula el reloj por sí mismo:

```powershell
.\scripts\capture_speedface_v5l_remaining.ps1 `
  -DeviceIp 192.168.68.201 `
  -Interface 1 `
  -Phase LabLifecycle `
  -ApprovalReference 'CHG-0000'
```

No se usan datos, tarjetas ni biometría de producción. Esta segunda fase
comprueba confirmación, idempotencia, campos permitidos y baja antes de que
ADMS habilite sincronización de personas reales.

## Historial local

La evidencia anterior se preservó, fuera de Git, en `captures/history/`:

- `2026-09-15_baseline_adms/`;
- `2026-09-17_realtime_and_info/`.

El asistente integral anterior está archivado y no debe ejecutarse; véase
`docs/archive/SPEEDFACE_V5L_FIELD_VALIDATION_20260917.md` sólo como historial.
