#!/bin/sh
set -eu
# The venv python is called directly; bin/activate and the "guppi" launcher hold the folder the venv was created in.
HERE=$(cd "$(dirname "$0")" && pwd)
PYTHONPATH="$HERE/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH
"$HERE/.venv/bin/python" -m guppi_runtime demo --intent "Create a GUPPI runtime demo artifact"
