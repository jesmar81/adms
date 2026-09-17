<#
Enterprise field-validation kit for a remote ZKTeco SpeedFace-V5L.

It is a passive packet capture except for the optional, read-only INFO probe.
It never proxies traffic, changes the terminal, adds users, or exports
biometrics. Raw captures and decoded streams can contain personal data.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F:.]+$')]
    [string]$DeviceIp,

    [string]$Interface,

    [ValidateRange(1, 65535)]
    [int]$ServerPort = 8000,

    [ValidateRange(180, 3600)]
    [int]$DurationSeconds = 900,

    [string]$OutputDirectory,

    # Optional and deliberately limited to the non-mutating INFO command.
    [switch]$QueueInfoProbe,
    [string]$ApiBaseUrl = 'http://127.0.0.1:8000',
    [string]$DeviceId,

    [switch]$ListInterfaces
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

throw 'ARCHIVED: la validación de checadas e INFO ya concluyó el 2026-09-17. Usa scripts/capture_speedface_v5l_remaining.ps1.'

function Find-WiresharkCommand([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $command) { return $command.Path }
    $candidate = Join-Path ${env:ProgramFiles} "Wireshark\$Name.exe"
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    throw "No se encontró $Name. Instala Wireshark incluyendo Npcap en este servidor."
}

function Add-Marker([string]$Timeline, [string]$Step, [string]$Result) {
    $entry = [pscustomobject]@{
        utc = [DateTime]::UtcNow.ToString('o')
        step = $Step
        result = $Result
    }
    $entry | Export-Csv -LiteralPath $Timeline -NoTypeInformation -Append -Encoding utf8
}

function Test-LocalListener([int]$Port) {
    try {
        return @(
            Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop
        ).Count -gt 0
    } catch {
        return $false
    }
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

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $repositoryRoot = Split-Path -Parent $PSScriptRoot
    $OutputDirectory = Join-Path $repositoryRoot 'captures'
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$startedAt = [DateTime]::UtcNow
$timestamp = $startedAt.ToString('yyyyMMddTHHmmssZ')
$safeIp = $DeviceIp.Replace(':', '_')
$base = Join-Path $OutputDirectory "speedface_v5l_validation_${safeIp}_${timestamp}"
$pcap = "$base.pcapng"
$timeline = "$base.timeline.csv"
$metadata = "$base.metadata.txt"
$decoded = "$base.decoded"
$summary = "$base.validation-summary.json"
$filter = "host $DeviceIp and tcp port $ServerPort"

@(
    "started_at_utc=$timestamp"
    "device_ip=$DeviceIp"
    "server_port=$ServerPort"
    "interface=$Interface"
    "bpf_filter=$filter"
    "computer_name=$env:COMPUTERNAME"
    "duration_seconds=$DurationSeconds"
    "queue_info_probe=$QueueInfoProbe"
) | Set-Content -LiteralPath $metadata -Encoding utf8

Write-Host ''
Write-Host '=== Validación real SpeedFace-V5L / Security PUSH ===' -ForegroundColor Cyan
Write-Host "PCAP crudo: $pcap"
Write-Host "Duración: $DurationSeconds segundos. No cierres esta ventana."
if (Test-LocalListener $ServerPort) {
    Write-Host "OK: se detectó un proceso escuchando el puerto local $ServerPort." -ForegroundColor Green
    Add-Marker $timeline 'preflight_listener' 'listening'
} else {
    Write-Warning "No se detectó un listener local en $ServerPort. Verifica Docker/firewall; la captura continúa para diagnóstico."
    Add-Marker $timeline 'preflight_listener' 'not_detected'
}
if (Test-Connection -ComputerName $DeviceIp -Count 1 -Quiet -ErrorAction SilentlyContinue) {
    Write-Host "OK: el reloj responde a ping ($DeviceIp)." -ForegroundColor Green
    Add-Marker $timeline 'preflight_device_ping' 'reachable'
} else {
    Write-Warning 'El reloj no respondió a ping; algunos equipos lo bloquean. Continúa si el ADMS está conectado.'
    Add-Marker $timeline 'preflight_device_ping' 'no_reply'
}

$dumpcapArgs = @('-i', $Interface, '-f', $filter, '-w', $pcap, '-a', "duration:$DurationSeconds")
$capture = Start-Process -FilePath $dumpcap -ArgumentList $dumpcapArgs -PassThru -NoNewWindow
Add-Marker $timeline 'capture_started' 'ok'
Start-Sleep -Seconds 3

try {
    Write-Host ''
    Write-Host 'Prueba 1/4: realiza DOS checadas con un PIN de laboratorio o personal autorizado.' -ForegroundColor Yellow
    Read-Host 'Al terminar ambas, presiona Enter para registrar la marca'
    Add-Marker $timeline 'two_realtime_checkins' 'operator_completed'

    if ($QueueInfoProbe) {
        if ([string]::IsNullOrWhiteSpace($DeviceId)) { throw '-DeviceId es obligatorio con -QueueInfoProbe.' }
        $secureToken = Read-Host 'Pega temporalmente un access token de administrador (no se guarda)' -AsSecureString
        $tokenBstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
        try {
            $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenBstr)
            $headers = @{ Authorization = "Bearer $token" }
            $body = @{ command_type = 'INFO'; params = @{} } | ConvertTo-Json -Compress
            $probe = Invoke-RestMethod -Method Post -Uri "$($ApiBaseUrl.TrimEnd('/'))/api/v1/devices/$DeviceId/commands" -Headers $headers -ContentType 'application/json' -Body $body
            Add-Marker $timeline 'info_probe_queued' "protocol_command_id=$($probe.protocol_command_id)"
            Write-Host "INFO encolado con ID $($probe.protocol_command_id). Espera al siguiente getrequest/devicecmd." -ForegroundColor Green
        } finally {
            if ($tokenBstr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenBstr) }
            Remove-Variable token -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host 'Prueba 2/4: en el panel web encola sólo INFO para este reloj; no uses UPDATE/DELETE/QUERY USERINFO.' -ForegroundColor Yellow
        Read-Host 'Cuando INFO esté encolado y el reloj haya vuelto a sondear, presiona Enter'
        Add-Marker $timeline 'info_probe_queued_manually' 'operator_completed'
    }

    Write-Host 'Prueba 3/4: si el menú del reloj tiene una función propia de cargar/consultar usuarios, ejecútala SIN altas ni bajas.' -ForegroundColor Yellow
    Write-Host 'Buscamos una llamada /iclock/querydata. Si no existe ese menú, deja esta prueba como no disponible.'
    Read-Host 'Cuando termine, presiona Enter'
    Add-Marker $timeline 'device_user_query' 'operator_completed_or_not_available'

    Write-Host 'Prueba 4/4: espera una checada adicional y al menos un ciclo normal de sondeo.' -ForegroundColor Yellow
    Read-Host 'Presiona Enter cuando termine'
    Add-Marker $timeline 'final_poll_and_checkin' 'operator_completed'

    $remaining = [Math]::Max(0, $DurationSeconds - [int](([DateTime]::UtcNow - $startedAt).TotalSeconds))
    if ($remaining -gt 0) {
        Write-Host "La captura seguirá $remaining segundos para no cortar respuestas tardías." -ForegroundColor Cyan
        Wait-Process -Id $capture.Id -Timeout ($remaining + 30) -ErrorAction SilentlyContinue
    }
} finally {
    if (-not $capture.HasExited) {
        Write-Host 'Cerrando captura de forma controlada...' -ForegroundColor Cyan
        Stop-Process -Id $capture.Id -ErrorAction SilentlyContinue
        $capture.WaitForExit()
    }
}

if (-not (Test-Path -LiteralPath $pcap)) { throw 'dumpcap no produjo un archivo PCAPNG.' }
$hash = (Get-FileHash -LiteralPath $pcap -Algorithm SHA256).Hash
Add-Content -LiteralPath $metadata -Value "sha256=$hash"

& $PSScriptRoot\decode_adms_pcap.ps1 -Capture $pcap -ServerPort $ServerPort -OutputDirectory $decoded
if ($LASTEXITCODE -ne 0) { throw "tshark no pudo decodificar la captura (código $LASTEXITCODE)." }

$httpSummary = Join-Path $decoded 'http-summary.tsv'
$rows = if (Test-Path -LiteralPath $httpSummary) { Import-Csv -LiteralPath $httpSummary -Delimiter "`t" } else { @() }
function Count-Uri([string]$Fragment) { return @($rows | Where-Object { $_.'http.request' -eq '1' -and $_.'http.request.uri' -like "*$Fragment*" }).Count }
$report = [ordered]@{
    capture = Split-Path -Leaf $pcap
    sha256 = $hash
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    requests = [ordered]@{
        getrequest = Count-Uri '/iclock/getrequest'
        rtstate = Count-Uri 'table=rtstate'
        rtlog = Count-Uri 'table=rtlog'
        querydata = Count-Uri '/iclock/querydata'
        devicecmd = Count-Uri '/iclock/devicecmd'
        registry = Count-Uri '/iclock/registry'
        push = Count-Uri '/iclock/push'
    }
    http_error_responses = @($rows | Where-Object { $_.'http.response' -eq '1' -and $_.'http.response.code' -match '^[45]' }).Count
    next_step = 'Entrega sólo el PCAP, metadata, timeline y validation-summary al responsable técnico por canal privado. No los subas a Git.'
}
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $summary -Encoding utf8

Write-Host ''
Write-Host '=== Resultado ===' -ForegroundColor Cyan
Write-Host "PCAP: $pcap"
Write-Host "Resumen seguro: $summary"
Write-Host "Transcripciones sensibles: $decoded"
Write-Host ("getrequest={0}; rtlog={1}; rtstate={2}; querydata={3}; devicecmd={4}" -f $report.requests.getrequest, $report.requests.rtlog, $report.requests.rtstate, $report.requests.querydata, $report.requests.devicecmd)
Write-Host 'No subas estos archivos al repositorio: contienen identificadores, horarios y posibles cookies.' -ForegroundColor Yellow
