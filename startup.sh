#!/bin/sh
set -eu

MODE="${1:-import-daemon}"
if [ "$#" -gt 0 ]; then
  shift
fi

exec python app.py --mode "$MODE" "$@"
