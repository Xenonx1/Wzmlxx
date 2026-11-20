#!/bin/bash
ARIA2C=$1

# fall back to the normal program name if the alias is missing
if ! command -v "$ARIA2C" >/dev/null 2>&1; then
    for c in aria2c /usr/bin/aria2c /usr/local/bin/aria2c; do
        if command -v "$c" >/dev/null 2>&1; then ARIA2C=$c; break; fi
    done
fi

tracker_list=$(curl -Ns --max-time 15 https://ngosang.github.io/trackerslist/trackers_all_http.txt | awk '$0' | tr '\n\n' ',')

wait_rpc() {
    for _ in $(seq 1 "${1:-15}"); do
        if (echo > /dev/tcp/127.0.0.1/6800) 2>/dev/null; then return 0; fi
        sleep 1
    done
    return 1
}

echo "[setpkgs] starting aria2 using: $ARIA2C ($(command -v "$ARIA2C"))"

FULL_OPTS=(
    --allow-overwrite=true --auto-file-renaming=true --bt-enable-lpd=true --bt-detach-seed-only=true
    --bt-remove-unselected-file=true "--bt-tracker=[$tracker_list]" --bt-max-peers=0 --enable-rpc=true
    --rpc-max-request-size=1024M --max-connection-per-server=10 --max-concurrent-downloads=1000 --split=10
    --seed-ratio=0 --check-integrity=true --continue=true --daemon=true --disk-cache=16M --force-save=true
    --min-split-size=10M --follow-torrent=mem --check-certificate=false --optimize-concurrent-downloads=true
    --http-accept-gzip=true --max-file-not-found=0 --max-tries=20 --peer-id-prefix=-qB4520- --reuse-uri=true
    --content-disposition-default-utf8=true --user-agent=Wget/1.12 --peer-agent=qBittorrent/4.5.2
    --summary-interval=0 --max-upload-limit=1K --log=/tmp/aria2.log --log-level=warn
)

"$ARIA2C" "${FULL_OPTS[@]}" 2>/tmp/aria2.err
rc=$?
if wait_rpc 15; then
    echo "[setpkgs] aria2 RPC is up"
    exit 0
fi

echo "[setpkgs] aria2 did not start with full options (exit code $rc). stderr:"
cat /tmp/aria2.err 2>/dev/null
tail -n 20 /tmp/aria2.log 2>/dev/null

echo "[setpkgs] retrying with minimal options"
"$ARIA2C" --enable-rpc=true --rpc-max-request-size=1024M --max-concurrent-downloads=1000 \
    --allow-overwrite=true --auto-file-renaming=true --continue=true --seed-ratio=0 \
    --check-certificate=false --daemon=true --log=/tmp/aria2.log --log-level=warn 2>/tmp/aria2.err2
if wait_rpc 15; then
    echo "[setpkgs] aria2 RPC is up (minimal options)"
    exit 0
fi

echo "[setpkgs] aria2 STILL not running. stderr:"
cat /tmp/aria2.err2 2>/dev/null
tail -n 20 /tmp/aria2.log 2>/dev/null
"$ARIA2C" --version 2>&1 | head -n 2
exit 0
