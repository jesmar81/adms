#!/usr/bin/env bash
# Capture an unmodified, bidirectional ADMS HTTP session from the host that
# receives connections from a ZKTeco device.  This script deliberately does
# not proxy or alter traffic: the resulting PCAP is the diagnostic source.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/capture_adms_session.sh --device-ip IP [options]

Options:
  --device-ip IP       LAN IP of the clock (required).
  --server-port PORT   ADMS TCP port on this host (default: 8000).
  --interface IFACE    Capture interface (default: any on Linux).
  --output-dir DIR     Directory for the PCAP (default: ./captures).
  --duration SECONDS   Stop automatically after this many seconds. 0 waits
                       until Ctrl+C (default: 300).
  -h, --help           Show this help.

The capture contains personal data and session cookies. Keep the output out
of source control and transfer it only through an approved private channel.
EOF
}

device_ip=""
server_port="8000"
interface="any"
output_dir="$(pwd)/captures"
duration="300"

while (($#)); do
  case "$1" in
    --device-ip) device_ip="${2:-}"; shift 2 ;;
    --server-port) server_port="${2:-}"; shift 2 ;;
    --interface) interface="${2:-}"; shift 2 ;;
    --output-dir) output_dir="${2:-}"; shift 2 ;;
    --duration) duration="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$device_ip" ]]; then
  echo "--device-ip is required" >&2
  usage >&2
  exit 2
fi
if ! [[ "$device_ip" =~ ^[0-9a-fA-F:.]+$ ]]; then
  echo "Invalid device IP: $device_ip" >&2
  exit 2
fi
if ! [[ "$server_port" =~ ^[0-9]{1,5}$ ]] || ((server_port < 1 || server_port > 65535)); then
  echo "Invalid server port: $server_port" >&2
  exit 2
fi
if ! [[ "$duration" =~ ^[0-9]+$ ]]; then
  echo "--duration must be a non-negative number of seconds" >&2
  exit 2
fi
if ! command -v tcpdump >/dev/null 2>&1; then
  echo "tcpdump is required. Install it on the server that receives the clock." >&2
  exit 1
fi

mkdir -p "$output_dir"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
safe_ip="${device_ip//:/_}"
base="${output_dir%/}/adms_${safe_ip}_${timestamp}"
pcap_file="${base}.pcap"
metadata_file="${base}.metadata.txt"
filter="host $device_ip and tcp port $server_port"

{
  printf 'captured_at_utc=%s\n' "$timestamp"
  printf 'device_ip=%s\n' "$device_ip"
  printf 'server_port=%s\n' "$server_port"
  printf 'interface=%s\n' "$interface"
  printf 'bpf_filter=%s\n' "$filter"
  printf 'host=%s\n' "$(hostname)"
} > "$metadata_file"

echo "Capturing bidirectional ADMS traffic from $device_ip on port $server_port"
echo "PCAP: $pcap_file"
echo "Metadata: $metadata_file"
echo "Make a physical check-in and, if possible, trigger a user synchronization."
echo "Stop with Ctrl+C, or wait $duration seconds."

tcpdump_command=(sudo tcpdump -i "$interface" -nn -s 0 -U -w "$pcap_file" "$filter")
if ((duration == 0)); then
  exec "${tcpdump_command[@]}"
fi

if ! command -v timeout >/dev/null 2>&1; then
  echo "The 'timeout' command is unavailable; capture will run until Ctrl+C." >&2
  exec "${tcpdump_command[@]}"
fi

set +e
timeout --foreground --signal=INT "$duration" "${tcpdump_command[@]}"
capture_status=$?
set -e
if ((capture_status != 0 && capture_status != 124)); then
  exit "$capture_status"
fi

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$pcap_file" | tee -a "$metadata_file"
fi
echo "Capture completed. Decode it with scripts/decode_adms_pcap.sh --capture $pcap_file"
