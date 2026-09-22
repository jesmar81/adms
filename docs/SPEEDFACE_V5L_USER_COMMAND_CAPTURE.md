# Validación activa de usuarios — SpeedFace V5L

Las operaciones de consulta, alta, cambio y baja de usuarios permanecen
bloqueadas por defecto para un reloj A&C Security PUSH no validado. Durante
esta captura controlada se habilitan explícitamente con
`ZKTECO_ALLOW_UNVALIDATED_USER_COMMANDS=true`. Desactiva la bandera al terminar.
El enrolamiento de rostro, huella o palma sigue siendo presencial en el
equipo: esta aplicación registra y controla su flujo, pero no transmite ni
guarda plantillas biométricas.

## Antes de iniciar

- Instala Wireshark con Npcap en el servidor Windows que recibe al reloj.
- Ejecuta el backend ADMS en ese servidor y verifica que el reloj se conecte
  a su IP y puerto real. No uses la IP interna de Docker ni `localhost`.
- Antes de iniciar el backend de captura, define temporalmente:

  ```powershell
  $env:ZKTECO_ALLOW_UNVALIDATED_USER_COMMANDS = 'true'
  ```

  Reinicia el backend para que tome la variable. Al concluir, ciérralo,
  elimina la variable con
  `Remove-Item Env:ZKTECO_ALLOW_UNVALIDATED_USER_COMMANDS` y vuelve a iniciar
  con el valor seguro por defecto.
- Define un PIN de laboratorio nuevo, sin tarjeta, empleado, rostro, huella ni
  palma asociados. El capturador obliga a indicarlo.
- Usa una referencia de autorización o ticket para dejar claro quién aprobó el
  ciclo de alta, cambio y baja de ese PIN de laboratorio.

## Ejecución en Windows

Desde la raíz del repositorio:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\capture_speedface_v5l_user_commands.ps1 `
  -DeviceIp 192.168.68.201 `
  -ListInterfaces

.\scripts\capture_speedface_v5l_user_commands.ps1 `
  -DeviceIp 192.168.68.201 `
  -Interface 1 `
  -ServerPort 8000 `
  -LabPin ZKLAB2026 `
  -AuthorizationReference 'CHG-0000'
```

El asistente indica cinco pausas. Desde el panel ADMS realiza, en este orden:

1. Esperar un sondeo normal del reloj.
2. **Personal en reloj** → consultar usuarios.
3. Crear y encolar exclusivamente el PIN de laboratorio.
4. **Relojes → Comandos** → `UPDATE_USERINFO`, cambiando sólo el nombre del
   mismo PIN. Usa los parámetros:

   ```json
   {"pin":"ZKLAB2026","name":"ZK LAB ACTUALIZADO","privilege":"0","card":""}
   ```
5. Eliminar ese PIN desde **Personal en reloj**.

No ejecutes reinicios, cambios A&C/T&A PUSH, importaciones masivas ni
operaciones biométricas durante esta captura.

## Entrega de la evidencia

Los archivos nuevos quedan aislados en `captures/active-user-command-validation/`:

- `*.pcapng`: evidencia cruda y autoritativa;
- `*.metadata.txt`: parámetros y SHA-256;
- `*.timeline.csv`: hora UTC de cada acción manual;
- `*.response-summary.json`: indicadores de comandos/respuestas detectados;
- `*.decoded/streams/`: transcripción por flujo TCP para revisar el retorno.

Las capturas anteriores permanecen en `captures/history/`; los scripts y
guías previos se movieron a `scripts/archive/` y `docs/archive/`. No subas
ninguno de estos archivos a Git: contienen datos de red y potencialmente datos
personales.
