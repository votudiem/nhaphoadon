#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ -x .runtime/venv/bin/python ]; then
    if .runtime/venv/bin/python -c 'import sys; assert sys.version_info >= (3,10)' >/dev/null 2>&1; then
        exec .runtime/venv/bin/python bootstrap.py "$@"
    fi
fi
exec python3 bootstrap.py "$@"
