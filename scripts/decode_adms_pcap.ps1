<#
Create per-TCP-stream HTTP transcripts from an ADMS PCAP/PCAPNG on Windows.
The original capture remains the authoritative raw evidence.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$Capture,

    [ValidateRange(1, 65535)]
    [int]$ServerPort = 8000,

    [string]$OutputDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Find-Tshark {
    $command = Get-Command 'tshark' -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Path
    }

    $candidate = Join-Path ${env:ProgramFiles} 'Wireshark\\tshark.exe'
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }
    throw 'No se encontró tshark. Instala Wireshark en este servidor.'
}

$tshark = Find-Tshark
$Capture = (Resolve-Path -LiteralPath $Capture).Path
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = "$Capture.decoded"
}
$streamsDirectory = Join-Path $OutputDirectory 'streams'
New-Item -ItemType Directory -Path $streamsDirectory -Force | Out-Null

$decodeArguments = @('-r', $Capture, '-d', "tcp.port==$ServerPort,http")
$summaryArguments = $decodeArguments + @(
    '-Y', 'http.request || http.response',
    '-T', 'fields',
    '-E', 'header=y', '-E', 'separator=\\t', '-E', 'quote=d', '-E', 'occurrence=f',
    '-e', 'frame.number', '-e', 'frame.time_iso', '-e', 'tcp.stream',
    '-e', 'ip.src', '-e', 'tcp.srcport', '-e', 'ip.dst', '-e', 'tcp.dstport',
    '-e', 'http.request', '-e', 'http.response',
    '-e', 'http.request.method', '-e', 'http.host', '-e', 'http.request.uri',
    '-e', 'http.response.code', '-e', 'http.content_length'
)

& $tshark @summaryArguments | Set-Content -LiteralPath (Join-Path $OutputDirectory 'http-summary.tsv') -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    throw "tshark no pudo leer $Capture"
}

$streams = @(
    & $tshark @decodeArguments -Y "tcp.port == $ServerPort" -T fields -e tcp.stream |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Sort-Object -Unique
)
if ($LASTEXITCODE -ne 0) {
    throw "tshark no pudo enumerar los flujos TCP de $Capture"
}

foreach ($stream in $streams) {
    $output = Join-Path $streamsDirectory "tcp-stream-$stream.txt"
    & $tshark @decodeArguments -q -z "follow,tcp,ascii,$stream" |
        Set-Content -LiteralPath $output -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        throw "tshark no pudo decodificar el flujo TCP $stream"
    }
}

@(
    "capture=$Capture"
    "server_port=$ServerPort"
    "streams=$($streams.Count)"
) | Set-Content -LiteralPath (Join-Path $OutputDirectory 'README.txt') -Encoding utf8

Write-Host "Se decodificaron $($streams.Count) flujo(s) TCP en $OutputDirectory"
