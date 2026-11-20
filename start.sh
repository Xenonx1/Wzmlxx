#!/bin/bash
if [ -f /wzvenv/bin/activate ]; then
    source /wzvenv/bin/activate
elif [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi
exec python3 -m bot
