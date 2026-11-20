#!/bin/bash
ARIA2C=$1

tracker_list=$(curl -Ns --max-time 15 https://ngosang.github.io/trackerslist/trackers_all_http.txt | awk '$0' | tr '\n\n' ',')
$ARIA2C --allow-overwrite=true --auto-file-renaming=true --bt-enable-lpd=true --bt-detach-seed-only=true \
       --bt-remove-unselected-file=true --bt-tracker="[$tracker_list]" --bt-max-peers=0 --enable-rpc=true \
       --rpc-max-request-size=1024M --max-connection-per-server=10 --max-concurrent-downloads=1000 --split=10 \
       --seed-ratio=0 --check-integrity=true --continue=true --daemon=true --disk-cache=40M --force-save=true \
       --min-split-size=10M --follow-torrent=mem --check-certificate=false --optimize-concurrent-downloads=true \
       --http-accept-gzip=true --max-file-not-found=0 --max-tries=20  --peer-id-prefix=-qB4520- --reuse-uri=true \
       --content-disposition-default-utf8=true --user-agent=Wget/1.12 --peer-agent=qBittorrent/4.5.2 \
       --summary-interval=0 --max-upload-limit=1K --log=/tmp/aria2.log --log-level=warn

# wait (up to 20s) until the aria2 RPC port answers, so the bot does not connect too early
for i in $(seq 1 20); do
    if (echo > /dev/tcp/127.0.0.1/6800) 2>/dev/null; then
        echo "aria2 RPC is up"
        exit 0
    fi
    sleep 1
done
echo "aria2 RPC did NOT start. Last aria2 log lines:"
tail -n 30 /tmp/aria2.log 2>/dev/null
exit 1
