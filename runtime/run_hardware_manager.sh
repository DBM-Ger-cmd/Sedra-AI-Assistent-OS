#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -m sedra_runtime --root . hardware-dashboard --open
