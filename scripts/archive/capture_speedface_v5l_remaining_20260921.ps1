<#
Capture only the still-unknown Security PUSH user-management wire protocol for
a SpeedFace-V5L. It is passive: it never sends a command to the device or
changes its configuration. The operator performs the indicated operation in
an already-authorized management system while dumpcap records the exchange.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F:.]+$')]
    [string]$DeviceIp,

    [string]$Interface,

    [ValidateRange(1, 65535)]
    [int]$ServerPort = 8000,

    [ValidateSet('UserRead', 'LabLifecycle')]
    [string]$Phase = 'UserRead',

    [ValidateRange(600, 3600)]
    [int]$DurationSeconds = 1800,

    [string]$OutputDirectory,

    # A human approval/change ticket is required before the lab-only phase.
    [string]$ApprovalReference,

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
    throw 'Indica -Interface. Primero puedes ejecutar este script con -ListInterfaces.'
}
if ($Phase -eq 'LabLifecycle' -and [string]::IsNullOrWhiteSpace($ApprovalReference)) {
    throw 'LabLifecycle requiere -ApprovalReference de la aprobación para el PIN de laboratorio.'
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $repositoryRoot = Split-Path -Parent $PSScriptRoot
    $OutputDirectory = Join-Path $repositoryRoot 'captures\pending'
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$startedAt = [DateTime]::UtcNow
$timestamp = $startedAt.ToString('yyyyMMddTHHmmssZ')
$safeIp = $DeviceIp.Replace(':', '_')
$base = Join-Path $OutputDirectory "speedface_v5l_user_${Phase}_${safeIp}_${timestamp}"
$pcap = "$base.pcapng"
$timeline = "$base.timeline.csv"
$metadata = "$base.metadata.txt"
$decoded = "$base.decoded"
$summary = "$base.evidence-summary.json"
$filter = "host $DeviceIp and tcp port $ServerPort"

@(
    "started_at_utc=$timestamp"
    "device_ip=$DeviceIp"
    "server_port=$ServerPort"
    "interface=$Interface"
    "phase=$Phase"
    "bpf_filter=$filter"
    "computer_name=$env:COMPUTERNAME"
    "duration_seconds=$DurationSeconds"
    "approval_reference=$ApprovalReference"
) | Set-Content -LiteralPath $metadata -Encoding utf8

Write-Host ''
Write-Host '=== Evidencia pendiente SpeedFace-V5L / Security PUSH ===' -ForegroundColor Cyan
Write-Host 'Esta herramienta sólo captura red. No encola comandos ni modifica el reloj.' -ForegroundColor Green
Write-Host "PCAP crudo: $pcap"
Write-Host "Fase: $Phase. Duración máxima: $DurationSeconds segundos."

$capture = Start-Process -FilePath $dumpcap -ArgumentList @('-i', $Interface, '-f', $filter, '-w', $pcap, '-a', "duration:$DurationSeconds") -PassThru -NoNewWindow
Add-Marker $timeline 'capture_started' 'ok'
Start-Sleep -Seconds 3

try {
    if ($Phase -eq 'UserRead') {
        Write-Host ''
        Write-Host 'Paso 1/2: espera un ciclo normal getrequest/rtstate; no hagas checadas ni INFO.' -ForegroundColor Yellow
        Read-Host 'Presiona Enter después de 30 segundos de línea base'
        Add-Marker $timeline 'baseline_idle' 'operator_completed'

        Write-Host 'Paso 2/2: desde el sistema autorizado que ya administra ESTE reloj, ejecuta sólo "listar", "consultar" o "descargar usuarios desde dispositivo".' -ForegroundColor Yellow
        Write-Host 'No agregues, edites, borres, reinicies, exportes biometría ni cambies A&C/T&A PUSH.' -ForegroundColor Yellow
        Read-Host 'Cuando la consulta de sólo lectura termine y el reloj haya sondeado de nuevo, presiona Enter'
        Add-Marker $timeline 'user_inventory_read' 'operator_completed'
    } else {
        Write-Host ''
        Write-Host 'Fase de laboratorio autorizada. Usa exclusivamente un PIN de laboratorio nuevo y sin biometría.' -ForegroundColor Yellow
        Write-Host 'No uses personas, PIN, tarjetas ni plantillas de producción.' -ForegroundColor Yellow
        Read-Host 'Tras tomar la línea base, presiona Enter'
        Add-Marker $timeline 'baseline_idle' 'operator_completed'
        Read-Host 'Crea el usuario de laboratorio desde el sistema autorizado; espera confirmación y presiona Enter'
        Add-Marker $timeline 'lab_user_create' 'operator_completed'
        Read-Host 'Consulta/lista usuarios para confirmar el alta; presiona Enter'
        Add-Marker $timeline 'lab_user_read_after_create' 'operator_completed'
        Read-Host 'Modifica sólo el nombre visible del usuario de laboratorio; espera confirmación y presiona Enter'
        Add-Marker $timeline 'lab_user_update_display_name' 'operator_completed'
        Read-Host 'Vuelve a consultar/listar usuarios; presiona Enter'
        Add-Marker $timeline 'lab_user_read_after_update' 'operator_completed'
        Read-Host 'Elimina el usuario de laboratorio y confirma en el mismo sistema; presiona Enter'
        Add-Marker $timeline 'lab_user_delete' 'operator_completed'
        Read-Host 'Vuelve a consultar/listar para probar que ya no existe; presiona Enter'
        Add-Marker $timeline 'lab_user_read_after_delete' 'operator_completed'
    }

    $remaining = [Math]::Max(0, $DurationSeconds - [int](([DateTime]::UtcNow - $startedAt).TotalSeconds))
    if ($remaining -gt 0) {
        Write-Host "La captura continúa $remaining segundos para conservar respuestas tardías." -ForegroundColor Cyan
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
if ($LASTEXITCODE -ne 0) { throw "tshark no pudo decodificar la captura (código $LASTEXITCODE)." }

$httpSummary = Join-Path $decoded 'http-summary.tsv'
$rows = if (Test-Path -LiteralPath $httpSummary) { Import-Csv -LiteralPath $httpSummary -Delimiter "`t" } else { @() }
function Count-Uri([string]$Fragment) {
    return @($rows | Where-Object { $_.'http.request' -eq '1' -and $_.'http.request.uri' -like "*$Fragment*" }).Count
}

$counts = [ordered]@{
    getrequest = Count-Uri '/iclock/getrequest'
    querydata = Count-Uri '/iclock/querydata'
    cdata_user = Count-Uri 'table=user'
    userinfo = Count-Uri 'USERINFO'
    userdata = Count-Uri 'USERDATA'
    devicecmd = Count-Uri '/iclock/devicecmd'
}
$userTransportObserved = ($counts.querydata + $counts.cdata_user + $counts.userinfo + $counts.userdata) -gt 0
$report = [ordered]@{
    capture = Split-Path -Leaf $pcap
    sha256 = $hash
    phase = $Phase
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    requests = $counts
    user_transport_observed = $userTransportObserved
    http_error_responses = @($rows | Where-Object { $_.'http.response' -eq '1' -and $_.'http.response.code' -match '^[45]' }).Count
    next_step = if ($userTransportObserved) { 'Entregar PCAP, metadata, timeline y resumen por canal privado para validar el wire antes de implementar o repetir operaciones.' } else { 'No se observó transporte de usuarios. No pruebes escrituras: conserva la evidencia y captura la lectura desde el sistema autorizado correcto.' }
}
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $summary -Encoding utf8

Write-Host ''
Write-Host '=== Resultado ===' -ForegroundColor Cyan
Write-Host "PCAP: $pcap"
Write-Host "Resumen: $summary"
Write-Host ("querydata={0}; cdata_user={1}; userinfo={2}; userdata={3}; devicecmd={4}" -f $counts.querydata, $counts.cdata_user, $counts.userinfo, $counts.userdata, $counts.devicecmd)
if (-not $userTransportObserved) {
    Write-Warning 'No se observó un transporte de usuarios. No habilites altas, cambios o bajas con esta evidencia.'
}
Write-Host 'No subas PCAP ni transcripciones a Git: pueden contener PIN, nombres, tarjetas y cookies.' -ForegroundColor Yellow
