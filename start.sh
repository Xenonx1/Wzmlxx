
#!/usr/bin/env bash
set -Eeuo pipefail

cd /usr/src/app

# Activate Python environment
if [ -f /wzvenv/bin/activate ]; then
    source /wzvenv/bin/activate
elif [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

# Find Aria2 executable
if command -v aria2c >/dev/null 2>&1; then
    ARIA2_BIN="aria2c"
elif command -v blitzfetcher >/dev/null 2>&1; then
    ARIA2_BIN="blitzfetcher"
else
    echo "ERROR: Aria2 executable not found"
    exit 1
fi

echo "Starting Aria2 using $ARIA2_BIN..."

# Start Aria2 and wait for RPC
bash ./setpkgs.sh "$ARIA2_BIN"

echo "Aria2 startup completed."

# Start Telegram bot
echo "Starting WZML-X..."
exec python3 -m bot
