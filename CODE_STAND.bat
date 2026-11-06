@echo off
rem SEDRA - Code, den du in dieser Fassung noch nicht gesehen hast (SPEC_APPS_v1 G4), ausserhalb des Browsers ansehen und uebernehmen.
rem   CODE_STAND.bat <projekt> [--zeigen]     -> zeigt ihn (mit Diff, wo die gesehene Fassung vorliegt); --zeigen ist der Standard
rem   CODE_STAND.bat <projekt> --uebernehmen  -> der aktuelle Stand gilt als gesehen (z. B. nach eigener Arbeit oder git pull)
rem Projekt-ID wie in der Harness, Standard: sedra-entwicklung. Gleiche Ablage wie die Oberflaeche (workspace\SEDRA_OS\runtime_data\harness\code_stand).
rem Pfade und Python wie START_SEDRA.bat; schlanker Einstieg ohne die ganze Runtime (laeuft auch auf dem USB-Stick).
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "RT=%ROOT%\runtime"
set "PROJ=%ROOT%\workspace\SEDRA_OS"
set "PY=%RT%\portable\python\current\python.exe"
set "PYFLAGS=-I -B"
if exist "%PY%" goto :los
set "PY=%RT%\.venv\Scripts\python.exe"
set "PYFLAGS=-B"
set "PYTHONPATH=%RT%\src"
if exist "%PY%" goto :los
echo Kein Python gefunden (weder runtime\portable\python\current noch runtime\.venv). Erst START_SEDRA.bat ausfuehren.
exit /b 2

:los
if "%~1"=="" (
  echo Aufruf: CODE_STAND.bat ^<projekt^> [--zeigen ^| --uebernehmen]   z. B. CODE_STAND.bat sedra-entwicklung
  exit /b 2
)
cd /d "%RT%"
"%PY%" %PYFLAGS% -m sedra_runtime.harness.code_stand --root "%PROJ%" %*
exit /b %ERRORLEVEL%
