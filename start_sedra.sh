#!/bin/sh
# Start of SEDRA on macOS and Linux (the counterpart of START_GUPPI.bat). First run: creates runtime/.venv with the system python3 and
# installs PyYAML (and dulwich when reachable). Then the UIX opens as its own window (Chrome/Edge/Chromium app mode) or in the browser.
# Ohne Argument: die Übersicht der Oberflächen (Start). ./start_sedra.sh cockpit: direkt in diese Oberfläche (nur dieser Start).
# ./start_sedra.sh --gewaehlt: die in uix.yaml gewählte. Weitere Optionen werden durchgereicht (--open, --replace). Fenster zu = Server aus.
set -eu
SHELLARG="--uebersicht"
REST=""
for a in "$@"; do
  case "$a" in
    --gewaehlt) SHELLARG="" ;;
    --uebersicht) SHELLARG="--uebersicht" ;;
    --*) REST="$REST $a" ;;
    *) SHELLARG="--shell $a" ;;
  esac
done
HERE=$(cd "$(dirname "$0")" && pwd)
RUNTIME="$HERE/runtime"
PROJECT="$HERE/workspace/GUPPI_OS"
ARCH="$HERE/architecture/GUPPI_Architecture_v1.20_SELF_DEVELOPMENT"
mkdir -p "$PROJECT"

if [ ! -x "$RUNTIME/.venv/bin/python" ]; then
  PY=$(command -v python3 || true)
  if [ -z "$PY" ]; then
    echo "python3 fehlt. macOS: 'xcode-select --install' oder python.org (3.11 oder neuer); Linux: Paket python3 und python3-venv." >&2
    exit 2
  fi
  echo "Ersteinrichtung: Python-Umgebung in runtime/.venv (einmalig)."
  "$PY" -m venv --system-site-packages "$RUNTIME/.venv"     # a PyYAML of the system python counts, so an offline PC can start too
  VPY="$RUNTIME/.venv/bin/python"
  if ! "$VPY" -c "import yaml" 2>/dev/null; then
    "$VPY" -m pip install --quiet "PyYAML>=6.0" || { echo "PyYAML konnte nicht installiert werden (kein Netz?). Offline: PyYAML-Wheel mit runtime/.venv/bin/pip install <datei.whl> einspielen." >&2; rm -rf "$RUNTIME/.venv"; exit 3; }
  fi
  "$VPY" -c "import dulwich" 2>/dev/null || "$VPY" -m pip install --quiet "dulwich==1.2.17" "urllib3>=2.2.2" || echo "Hinweis: dulwich nicht installiert (nur für die DevVM nötig; später mit runtime/.venv/bin/pip nachholen)."
fi

cd "$RUNTIME"
PYTHONPATH="$RUNTIME/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONPATH
# shellcheck disable=SC2086
exec "$RUNTIME/.venv/bin/python" -B -m guppi_runtime.uix_start --root "$PROJECT" --architecture "$ARCH" $SHELLARG $REST
