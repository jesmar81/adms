#!/usr/bin/env bash
# Produce shareable, per-TCP-stream HTTP transcripts from a PCAP captured by
# capture_adms_session.sh. The PCAP remains the authoritative raw evidence.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/decode_adms_pcap.sh --capture FILE [options]

Options:
  --capture FILE       PCAP or PCAPNG file to decode (required).
  --server-port PORT   ADMS TCP port (default: 8000).
  --output-dir DIR     Directory for decoded files (default: <capture>.decoded).
  -h, --help           Show this help.

Output:
  http-summary.tsv     One row per parsed HTTP request or response.
  streams/             Complete ASCII transcript for each TCP stream.

The output includes identifiers, cards, check-in data and session tokens.
Treat it as sensitive diagnostic material.
EOF
}

capture=""
server_port="8000"
output_dir=""

while (($#)); do
  case "$1" in
    --capture) capture="${2:-}"; shift 2 ;;
    --server-port) server_port="${2:-}"; shift 2 ;;
    --output-dir) output_dir="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$capture" || ! -f "$capture" ]]; then
  echo "--capture must point to an existing PCAP file" >&2
  exit 2
fi
if ! [[ "$server_port" =~ ^[0-9]{1,5}$ ]] || ((server_port < 1 || server_port > 65535)); then
  echo "Invalid server port: $server_port" >&2
  exit 2
fi
if ! command -v tshark >/dev/null 2>&1; then
  echo "tshark is required to decode PCAP files (Wireshark CLI)." >&2
  exit 1
fi

if [[ -z "$output_dir" ]]; then
  output_dir="${capture}.decoded"
fi
mkdir -p "$output_dir/streams"

decode=(tshark -r "$capture" -d "tcp.port==$server_port,http")

"${decode[@]}" \
  -Y 'http.request || http.response' \
  -T fields \
  -E header=y -E separator=$'\t' -E quote=d -E occurrence=f \
  -e frame.number -e frame.time_iso -e tcp.stream \
  -e ip.src -e tcp.srcport -e ip.dst -e tcp.dstport \
  -e http.request -e http.response \
  -e http.request.method -e http.host -e http.request.uri \
  -e http.response.code -e http.content_length \
  > "$output_dir/http-summary.tsv"

mapfile -t streams < <(
  "${decode[@]}" -Y "tcp.port == $server_port" -T fields -e tcp.stream \
    | LC_ALL=C sort -n -u
)

for stream in "${streams[@]}"; do
  [[ -n "$stream" ]] || continue
  "${decode[@]}" -q -z "follow,tcp,ascii,$stream" \
    > "$output_dir/streams/tcp-stream-${stream}.txt"
done

printf 'capture=%s\nserver_port=%s\nstreams=%s\n' \
  "$capture" "$server_port" "${#streams[@]}" > "$output_dir/README.txt"
echo "Decoded ${#streams[@]} TCP stream(s) into $output_dir"
