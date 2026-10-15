#!/bin/sh
set -eu
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
echo "GUPPI runtime environment ready."
