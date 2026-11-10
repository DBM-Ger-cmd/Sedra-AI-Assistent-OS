@echo off
rem SEDRA als Agent im Terminal (Orca): startet einen eigenen SEDRA-Server im Hintergrund und chattet hier.
rem   SEDRA_AGENT.bat                  -> Chat im Terminal (/ende beendet)
rem   SEDRA_AGENT.bat --einmal "Frage" -> eine Antwort ausgeben, beenden
rem   SEDRA_AGENT.bat --replace        -> ein schon laufendes SEDRA vorher beenden
rem Orca: Einstellungen > Agenten > Eintrag (z. B. Hermes) > Startbefehl = voller Pfad dieser Datei. Siehe docs\ORCA_ANBINDUNG.md
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "RT=%ROOT%\runtime"
set "PY=%RT%\portable\python\current\python.exe"
if not exist "%PY%" set "PY=%RT%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Die Python-Umgebung fehlt. Einmal START_SEDRA.bat ausfuehren.
  exit /b 2
)
set "PYTHONUTF8=1"
set "PYTHONPATH=%RT%\src"
"%PY%" -B -X utf8 -m sedra_runtime.harness.orca_bruecke --root "%ROOT%" --python "%PY%" %*
exit /b %errorlevel%
