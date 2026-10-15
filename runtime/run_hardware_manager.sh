#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -m guppi_runtime --root . hardware-dashboard --open
