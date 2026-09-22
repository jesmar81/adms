<#
Capture unmodified, bidirectional ADMS HTTP traffic on Windows.  dumpcap is
the Wireshark capture utility and uses Npcap; it does not act as a proxy.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-fA-F:.]+$')]
    [string]$DeviceIp,

    [ValidateRange(1, 65535)]
    [int]$ServerPort = 8000,

    # Obtain valid values with: & 'C:\Program Files\Wireshark\dumpcap.exe' -D
    [string]$Interface,

    [string]$OutputDirectory,

    # Set to 0 to stop manually with Ctrl+C.
    [ValidateRange(0, 86400)]
    [int]$DurationSeconds = 600,

    [switch]$ListInterfaces
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Find-WiresharkCommand([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Path
    }

    $candidate = Join-Path ${env:ProgramFiles} "Wireshark\\$Name.exe"
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }
    throw "No se encontró $Name. Instala Wireshark con Npcap en este servidor."
}

$dumpcap = Find-WiresharkCommand 'dumpcap'
if ($ListInterfaces) {
    & $dumpcap -D
    exit $LASTEXITCODE
}

if ([string]::IsNullOrWhiteSpace($Interface)) {
    Write-Host 'Primero identifica la interfaz conectada a la LAN del reloj:' -ForegroundColor Yellow
    & $dumpcap -D
    Write-Error 'Indica el número o identificador con -Interface. Ejemplo: -Interface 1'
    exit 2
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $repositoryRoot = Split-Path -Parent $PSScriptRoot
    $OutputDirectory = Join-Path $repositoryRoot 'captures'
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$timestamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$safeIp = $DeviceIp.Replace(':', '_')
$base = Join-Path $OutputDirectory "adms_${safeIp}_${timestamp}"
$pcap = "$base.pcapng"
$metadata = "$base.metadata.txt"
$filter = "host $DeviceIp and tcp port $ServerPort"

@(
    "captured_at_utc=$timestamp"
    "device_ip=$DeviceIp"
    "server_port=$ServerPort"
    "interface=$Interface"
    "bpf_filter=$filter"
    "computer_name=$env:COMPUTERNAME"
) | Set-Content -LiteralPath $metadata -Encoding utf8

$arguments = @('-i', $Interface, '-f', $filter, '-w', $pcap)
if ($DurationSeconds -gt 0) {
    $arguments += @('-a', "duration:$DurationSeconds")
}

Write-Host "Capturando tráfico ADMS bidireccional desde $DeviceIp en puerto $ServerPort"
Write-Host "Archivo crudo: $pcap"
Write-Host 'Realiza dos checadas físicas y, si existe, una sincronización de usuarios.'
if ($DurationSeconds -eq 0) {
    Write-Host 'La captura continuará hasta que presiones Ctrl+C.'
} else {
    Write-Host "La captura terminará automáticamente en $DurationSeconds segundos."
}

& $dumpcap @arguments
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "dumpcap terminó con código $exitCode"
}

if (Test-Path -LiteralPath $pcap) {
    $hash = (Get-FileHash -LiteralPath $pcap -Algorithm SHA256).Hash
    Add-Content -LiteralPath $metadata -Value "sha256=$hash"
}
Write-Host "Captura terminada. Decodifica con: .\\scripts\\decode_adms_pcap.ps1 -Capture '$pcap'"
