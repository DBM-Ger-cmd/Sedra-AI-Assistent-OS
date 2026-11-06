#!/bin/sh
# Start of SEDRA on macOS and Linux (the counterpart of START_SEDRA.bat). First run: creates runtime/.venv with the system python3 and
# installs PyYAML (and dulwich when reachable). Then the UIX opens as its own window (Chrome/Edge/Chromium app mode) or in the browser.
# Ohne Argument: gleich One Sedra, keine Auswahl (die anderen Oberflächen wählt man in den Menüs). ./start_sedra.sh cockpit: direkt in diese Oberfläche (nur dieser Start).
# ./start_sedra.sh --gewaehlt: die in uix.yaml gewählte. Weitere Optionen werden durchgereicht (--open, --replace). Fenster zu = Server aus.
set -eu
SHELLARG="--shell harness"
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
PROJECT="$HERE/workspace/SEDRA_OS"
ARCH="$HERE/architecture/SEDRA_Architecture_v1.20_SELF_DEVELOPMENT"
# Übergang vom alten Ordnernamen (vor 1.23.0); der alte Name ist absichtlich zerlegt, damit er sonst nirgends vorkommt.
ALT="GUP""PI_OS"
if [ -d "$HERE/workspace/$ALT" ] && [ ! -e "$PROJECT" ]; then mv "$HERE/workspace/$ALT" "$PROJECT"; fi
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
"$RUNTIME/.venv/bin/python" -B -m sedra_runtime.legacy_names --root "$HERE" || true
# shellcheck disable=SC2086
exec "$RUNTIME/.venv/bin/python" -B -m sedra_runtime.uix_start --root "$PROJECT" --architecture "$ARCH" $SHELLARG $REST
