# Historial: validación completa del SpeedFace‑V5L remoto (Windows)

> Archivado el 2026-09-17. Esta validación ya se completó y su script fue
> desactivado para evitar duplicar checadas e `INFO`. Para evidencia activa usa
> [`SPEEDFACE_V5L_REMAINING_CAPTURE.md`](../SPEEDFACE_V5L_REMAINING_CAPTURE.md).

Este procedimiento crea evidencia real para completar la integración sin
adivinar comandos ni transportar biometría. Se ejecuta **en el servidor Windows
que recibe al reloj**, no en la computadora desde la que administras el
proyecto.

## Una sola ejecución

1. Instala Wireshark e incluye Npcap.
2. Abre PowerShell desde la raíz del repositorio y permite scripts sólo en esa
   ventana:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\validate_speedface_v5l.ps1 -DeviceIp 192.168.68.201 -ListInterfaces
```

3. Identifica la interfaz LAN y ejecuta (por ejemplo, interfaz `1`):

```powershell
.\scripts\validate_speedface_v5l.ps1 `
  -DeviceIp 192.168.68.201 `
  -Interface 1 `
  -ServerPort 8000
```

El asistente mantiene 15 minutos de captura y te guía para hacer dos
checadas, un `INFO` inocuo desde el panel, una consulta local de usuarios si
el menú existe y una checada final. Al terminar crea:

- `*.pcapng`: evidencia cruda y autoritativa;
- `*.metadata.txt`: filtro, interfaz y SHA-256;
- `*.timeline.csv`: hora de cada paso operado;
- `*.validation-summary.json`: sólo conteos de endpoints, seguro para revisión
  inicial;
- `*.decoded/`: transcripciones completas **sensibles**.

## Variante con INFO automático

Para evitar abrir el panel durante la prueba, el script puede encolar sólo
`INFO`. Solicita el token de forma oculta y no lo escribe en archivos ni en la
línea de comandos:

```powershell
.\scripts\validate_speedface_v5l.ps1 `
  -DeviceIp 192.168.68.201 `
  -Interface 1 `
  -QueueInfoProbe `
  -DeviceId 'UUID-del-reloj'
```

No actives ni pruebes `UPDATE_USERINFO`, `DELETE_USERINFO`, consulta legacy de
usuarios, cambios de tipo A&C/T&A PUSH, ni operaciones de plantillas durante
esta captura. Esas acciones requieren primero observar el wire exacto de este
firmware.

## Entrega privada

Conserva todos los archivos fuera de Git. El PCAP puede contener PIN, nombre,
tarjeta, hora de checada y cookies. Para una revisión inicial basta compartir
el JSON de resumen; para implementar el adaptador se requiere el PCAP o las
transcripciones mediante un canal privado autorizado.
