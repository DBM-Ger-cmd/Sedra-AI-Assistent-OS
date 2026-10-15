#!/bin/sh
set -eu
# The venv's python is called directly (bin/activate holds the folder the venv was created in).
# src: the package also runs without "pip install -e ."; tests: shared helpers such as host_isolation.py
HERE=$(cd "$(dirname "$0")" && pwd)
PYTHONPATH="$HERE/src:$HERE/tests${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH
"$HERE/.venv/bin/python" -m unittest discover -s "$HERE/tests" -t "$HERE/tests" -v
