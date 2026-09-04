#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

HOST_VALUE="${HOST:-127.0.0.1}"
SESSION_SECRET_VALUE="${SESSION_SECRET:-}"
if [ "$HOST_VALUE" != "127.0.0.1" ] && [ "$HOST_VALUE" != "localhost" ]; then
  if [ -z "${APP_PASSWORD:-}" ] || [ "${#SESSION_SECRET_VALUE}" -lt 32 ]; then
    echo "非本机监听必须设置 APP_PASSWORD 和至少32字符的 SESSION_SECRET" >&2
    exit 1
  fi
fi

exec "$PYTHON_BIN" -m uvicorn app.main:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
