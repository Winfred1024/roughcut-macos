#!/bin/bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"
exec "${CUT_PYTHON:-python3}" "$BASE/deploy/launch.py" "$@"
