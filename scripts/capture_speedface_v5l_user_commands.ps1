<#
Capture the real SpeedFace-V5L response while ADMS queues the enabled user
commands.  This script is passive: it starts dumpcap and records timestamps;
it never calls the API, sends a command, or changes device configuration.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F:.]+$')]
    [string]$DeviceIp,

    [string]$Interface,

    [ValidateRange(1, 65535)]
    [int]$ServerPort = 8000,

    # Use a new, disposable PIN. Never use an employee PIN or biometric data.
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9_-]{1,64}$')]
    [string]$LabPin,

    [Parameter(Mandatory = $true)]
    [ValidateLength(3, 120)]
    [string]$AuthorizationReference,

    [ValidateRange(900, 3600)]
    [int]$DurationSeconds = 1800,

    [string]$OutputDirectory,

    [switch]$ListInterfaces
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Find-WiresharkCommand([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $command) { return $command.Path }
    $candidate = Join-Path ${env:ProgramFiles} "Wireshark\$Name.exe"
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    throw "No se encontró $Name. Instala Wireshark incluyendo Npcap en este servidor."
}

function Add-Marker([string]$Timeline, [string]$Step, [string]$Result) {
    [pscustomobject]@{
        utc = [DateTime]::UtcNow.ToString('o')
        step = $Step
        result = $Result
    } | Export-Csv -LiteralPath $Timeline -NoTypeInformation -Append -Encoding utf8
}

$dumpcap = Find-WiresharkCommand 'dumpcap'
$tshark = Find-WiresharkCommand 'tshark'
if ($ListInterfaces) {
    & $dumpcap -D
    exit $LASTEXITCODE
}
if ([string]::IsNullOrWhiteSpace($Interface)) {
    throw 'Indica -Interface. Primero ejecuta este script con -ListInterfaces.'
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $repositoryRoot = Split-Path -Parent $PSScriptRoot
    $OutputDirectory = Join-Path $repositoryRoot 'captures\active-user-command-validation'
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$startedAt = [DateTime]::UtcNow
$timestamp = $startedAt.ToString('yyyyMMddTHHmmssZ')
$safeIp = $DeviceIp.Replace(':', '_')
$base = Join-Path $OutputDirectory "speedface_v5l_user_commands_${safeIp}_${timestamp}"
$pcap = "$base.pcapng"
$timeline = "$base.timeline.csv"
$metadata = "$base.metadata.txt"
$decoded = "$base.decoded"
$summary = "$base.response-summary.json"
$filter = "host $DeviceIp and tcp port $ServerPort"

@(
    "started_at_utc=$timestamp"
    "device_ip=$DeviceIp"
    "server_port=$ServerPort"
    "interface=$Interface"
    "lab_pin=$LabPin"
    "authorization_reference=$AuthorizationReference"
    "duration_seconds=$DurationSeconds"
    "bpf_filter=$filter"
    "computer_name=$env:COMPUTERNAME"
) | Set-Content -LiteralPath $metadata -Encoding utf8

Write-Host ''
Write-Host '=== Captura de comandos de usuario SpeedFace-V5L ===' -ForegroundColor Cyan
Write-Host "PIN de laboratorio autorizado: $LabPin" -ForegroundColor Yellow
Write-Host 'Este asistente no envía nada. Los comandos se ejecutan desde el panel ADMS.' -ForegroundColor Green
Write-Host "PCAP crudo: $pcap"

$capture = Start-Process -FilePath $dumpcap -ArgumentList @('-i', $Interface, '-f', $filter, '-w', $pcap, '-a', "duration:$DurationSeconds") -PassThru -NoNewWindow
Add-Marker $timeline 'capture_started' 'ok'
Start-Sleep -Seconds 3

try {
    Write-Host ''
    Read-Host 'Paso 1/5: espera un sondeo normal del reloj y presiona Enter'
    Add-Marker $timeline 'baseline_poll' 'operator_completed'

    Write-Host 'Paso 2/5: en Personal en reloj, ejecuta "Consultar usuarios del reloj". Espera respuesta y presiona Enter.' -ForegroundColor Yellow
    Read-Host
    Add-Marker $timeline 'query_userinfo' 'operator_completed'

    Write-Host "Paso 3/5: crea y encola SOLAMENTE el PIN $LabPin desde Personal en reloj. Espera respuesta y presiona Enter." -ForegroundColor Yellow
    Read-Host
    Add-Marker $timeline 'update_userinfo_create' 'operator_completed'

    Write-Host "Paso 4/5: en Relojes > Comandos, ejecuta UPDATE_USERINFO para el PIN $LabPin cambiando sólo el nombre visible. Espera respuesta y presiona Enter." -ForegroundColor Yellow
    Read-Host
    Add-Marker $timeline 'update_userinfo_display_name' 'operator_completed'

    Write-Host "Paso 5/5: elimina el PIN de laboratorio $LabPin desde Personal en reloj. Espera respuesta y presiona Enter." -ForegroundColor Yellow
    Read-Host
    Add-Marker $timeline 'delete_userinfo' 'operator_completed'

    $remaining = [Math]::Max(0, $DurationSeconds - [int](([DateTime]::UtcNow - $startedAt).TotalSeconds))
    if ($remaining -gt 0) {
        Write-Host "Conservando $remaining segundos para respuestas tardías..." -ForegroundColor Cyan
        Wait-Process -Id $capture.Id -Timeout ($remaining + 30) -ErrorAction SilentlyContinue
    }
} finally {
    if (-not $capture.HasExited) {
        Stop-Process -Id $capture.Id -ErrorAction SilentlyContinue
        $capture.WaitForExit()
    }
}

if (-not (Test-Path -LiteralPath $pcap)) { throw 'dumpcap no produjo un PCAPNG.' }
$hash = (Get-FileHash -LiteralPath $pcap -Algorithm SHA256).Hash
Add-Content -LiteralPath $metadata -Value "sha256=$hash"

& $PSScriptRoot\decode_adms_pcap.ps1 -Capture $pcap -ServerPort $ServerPort -OutputDirectory $decoded
if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear la transcripción de la captura.' }

$httpSummary = Join-Path $decoded 'http-summary.tsv'
$text = if (Test-Path -LiteralPath $httpSummary) { Get-Content -LiteralPath $httpSummary -Raw } else { '' }
$streamsDirectory = Join-Path $decoded 'streams'
$streamText = if (Test-Path -LiteralPath $streamsDirectory) {
    (Get-ChildItem -LiteralPath $streamsDirectory -Filter '*.txt' | Get-Content -Raw) -join "`n"
} else { '' }
[pscustomobject]@{
    capture = $pcap
    sha256 = $hash
    lab_pin = $LabPin
    authorization_reference = $AuthorizationReference
    command_poll_observed = "$text`n$streamText" -match 'getrequest|devicecmd'
    user_query_observed = "$text`n$streamText" -match 'QUERY USERINFO|querydata|USERINFO'
    update_observed = $streamText -match 'UPDATE USERINFO'
    delete_observed = $streamText -match 'DELETE USERINFO'
    decoded_directory = $decoded
    next_step = 'Entrega el PCAP, metadata, timeline, response-summary y carpeta decoded por canal privado.'
} | ConvertTo-Json | Set-Content -LiteralPath $summary -Encoding utf8

Write-Host ''
Write-Host "Captura terminada: $pcap" -ForegroundColor Green
Write-Host "Respuesta legible: $decoded\streams" -ForegroundColor Green
Write-Host "Resumen: $summary" -ForegroundColor Green
