# Captura de consulta de usuarios — SpeedFace V5L

La consulta `QUERY_USERINFO` es de sólo lectura y puede encolarse desde
**Personal en reloj → Consultar usuarios del reloj**. Las altas, cambios y
bajas siguen bloqueadas para el perfil A&C / Security PUSH hasta validar por
separado esos comandos. Esta captura sirve para comprobar si el firmware
responde a la consulta y en qué formato; no garantiza que la admita.

El enrolamiento de rostro, huella o palma sigue siendo presencial en el
equipo: esta aplicación registra y controla su flujo, pero no transmite ni
guarda plantillas biométricas.

## Antes de iniciar

- Instala Wireshark con Npcap en el servidor Windows que recibe al reloj.
- Ejecuta el backend ADMS en ese servidor y verifica que el reloj se conecte
  a su IP y puerto real. No uses la IP interna de Docker ni `localhost`.
- No habilites `ZKTECO_ALLOW_UNVALIDATED_USER_COMMANDS`: esa bandera también
  habilita escrituras. No se necesita para esta prueba de sólo lectura.

## Ejecución en Windows

Desde la raíz del repositorio:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\archive\capture_speedface_v5l_remaining_20260921.ps1 `
  -DeviceIp IP_REAL_DEL_RELOJ `
  -Interface NUMERO_DE_DUMPCAP `
  -ServerPort 8000 `
  -Phase UserRead `
  -DurationSeconds 600 `
  -OutputDirectory .\captures\pending
```

El asistente captura una línea base y después espera a que, en ADMS, abras
**Personal en reloj** y pulses **Consultar usuarios del reloj** una sola vez.
No ejecutes altas, cambios, bajas, reinicios, cambios A&C/T&A PUSH ni
operaciones biométricas durante esta captura.

## Entrega de la evidencia

Los archivos nuevos quedan aislados en `captures/pending/`:

- `*.pcapng`: evidencia cruda y autoritativa;
- `*.metadata.txt`: parámetros y SHA-256;
- `*.timeline.csv`: hora UTC de cada acción manual;
- `*.response-summary.json`: indicadores de comandos/respuestas detectados;
- `*.decoded/streams/`: transcripción por flujo TCP para revisar el retorno.

Las capturas anteriores permanecen en `captures/history/`; los scripts y
guías previos se movieron a `scripts/archive/` y `docs/archive/`. No subas
ninguno de estos archivos a Git: contienen datos de red y potencialmente datos
personales.
