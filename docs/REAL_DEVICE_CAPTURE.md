# Captura de una sesión real de reloj

Para diagnosticar un reloj ZKTeco de tipo Security PUSH se necesita el
intercambio HTTP completo, tanto las solicitudes del reloj como las respuestas
del servidor. Un log de Uvicorn no incluye cuerpos HTTP, y agregar un
middleware de depuración en Python perdería solicitudes rechazadas antes de la
aplicación o detalles de red. Por eso la fuente de evidencia es una captura
PCAP hecha en el **servidor que recibe al reloj**.

La captura es pasiva: no es un proxy y no modifica tráfico, configuración ni
datos del reloj.

> El PCAP y sus transcripciones contienen datos personales (PIN, tarjeta,
> nombres, horario de checada) y cookies de sesión. No los subas al repositorio
> ni los envíes por un canal público. La carpeta `captures/` está ignorada por
> Git.

## Windows (recomendado para el servidor remoto)

Instala [Wireshark](https://www.wireshark.org/download.html) en el servidor que
recibe al reloj e incluye **Npcap** durante el instalador. Wireshark provee
`dumpcap.exe` para capturar y `tshark.exe` para leer PCAP; no hace falta Python
ni modificar el backend.

El reloj debe apuntar a la IP LAN o DNS de este servidor y al puerto publicado
por ADMS (por defecto `8000`). Si el backend corre en Docker, use la IP del
host Windows, nunca una IP interna del contenedor o `localhost`.

Abre **PowerShell** desde la raíz del repositorio. Si Windows bloquea scripts
locales descargados, permite su ejecución solamente para esa ventana:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Identifica la interfaz conectada a la misma red del reloj:

```powershell
.\scripts\capture_adms_session.ps1 -DeviceIp 192.168.68.201 -ListInterfaces
```

El número de la interfaz mostrada por `dumpcap` no siempre coincide con el
adaptador visto en Configuración de Windows. Elige el que tenga la IP LAN del
servidor, por ejemplo `1`, y comienza la captura:

```powershell
.\scripts\capture_adms_session.ps1 `
  -DeviceIp 192.168.68.201 `
  -ServerPort 8000 `
  -Interface 1 `
  -DurationSeconds 600
```

Mientras se capturan diez minutos, realiza dos checadas de prueba y, si el
panel lo permite, una operación de sincronización de usuarios. El resultado
es un `.pcapng` crudo y un archivo de metadata en `captures/`.

Para crear la vista legible, sin alterar el archivo crudo:

```powershell
.\scripts\decode_adms_pcap.ps1 `
  -Capture .\captures\adms_192.168.68.201_FECHA.pcapng `
  -ServerPort 8000
```

La carpeta `*.pcapng.decoded\` contendrá `http-summary.tsv` y una
transcripción completa de cada flujo TCP en `streams\`.

## Linux (alternativa)

### Requisitos Linux

- Ejecutar los scripts de este repositorio.
- `tcpdump` para la captura. En Debian/Ubuntu: `sudo apt-get install tcpdump`.
- `tshark` (Wireshark CLI) para convertir el PCAP en texto, opcional pero
  recomendado: `sudo apt-get install tshark`.
- Acceso `sudo` solo para abrir la interfaz de red en modo captura.
- El reloj debe apuntar a la IP LAN o DNS de este servidor y al puerto publicado
  por ADMS (por defecto `8000`). Si el backend corre en Docker, use la IP del
  host, nunca la IP interna del contenedor.

## Capturar

Desde la raíz del repositorio, sustituye la IP por la del reloj remoto:

```bash
chmod +x scripts/capture_adms_session.sh scripts/decode_adms_pcap.sh
scripts/capture_adms_session.sh \
  --device-ip 192.168.68.201 \
  --server-port 8000 \
  --duration 600
```

El script crea dos archivos en `captures/`:

- `adms_<ip>_<fecha>.pcap`: evidencia cruda y autoritativa de ambos sentidos.
- `adms_<ip>_<fecha>.metadata.txt`: interfaz, filtro, hora y checksum.

Mientras corre la captura:

1. Haz dos checadas físicas con usuarios de prueba.
2. En el panel, intenta consultar o sincronizar usuarios si esa función existe.
3. Espera una reconexión normal. No reinicies ni restablezcas el reloj solo
   para capturar; si hace falta una captura de arranque se programa después.

Para observar rutas y estados HTTP en paralelo, sin ver cuerpos:

```bash
docker compose logs -f --tail=0 backend
```

Si el host tiene varias interfaces y `any` no captura el tráfico, identifica
la interfaz LAN con `ip -br address` y pásala, por ejemplo `--interface eth0`.

## Decodificar para análisis

El PCAP no se modifica. Para generar una vista de texto por flujo TCP:

```bash
scripts/decode_adms_pcap.sh \
  --capture captures/adms_192.168.68.201_YYYYMMDDTHHMMSSZ.pcap \
  --server-port 8000
```

Esto crea `*.pcap.decoded/` con:

- `http-summary.tsv`: método, URI, estado, IPs y flujo TCP.
- `streams/tcp-stream-N.txt`: petición y respuesta completas por conexión.

Para la corrección del protocolo se deben conservar y revisar el PCAP y las
transcripciones. Buscaremos, entre otras cosas, llamadas a `registry`, `push`,
`cdata` (`rtlog`, `rtstate`, `tabledata`, `options`), `getrequest`,
`devicecmd`, `querydata`, `rtdata` y `ping`; además de los valores
`CmdFormat`, `RegistryCode`, `SessionID` y los acuses de comando.

## Si no se ve tráfico

1. Confirma que la IP y puerto configurados en el reloj corresponden al host
   remoto, no a una dirección de Docker o `localhost`.
2. Comprueba que el puerto está publicado: `docker compose ps` y
   `curl --fail --silent --show-error http://127.0.0.1:8000/health` desde el
   host.
3. Repite usando la interfaz LAN explícita.
4. Conserva incluso un PCAP vacío y su metadata: demuestra que el problema es
   de conectividad antes de ADMS.
