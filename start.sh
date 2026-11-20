
#!/bin/bash

set -e

if [ -f /wzvenv/bin/activate ]; then
    source /wzvenv/bin/activate
elif [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

echo "Starting Aria2 RPC..."

if command -v aria2c >/dev/null 2>&1; then
    ARIA2_BIN="aria2c"
elif command -v blitzfetcher >/dev/null 2>&1; then
    ARIA2_BIN="blitzfetcher"
else
    echo "ERROR: Aria2 executable not found!"
    exit 1
fi

bash setpkgs.sh "$ARIA2_BIN"

echo "Starting WZML-X Telegram bot..."

exec python3 -m bot
