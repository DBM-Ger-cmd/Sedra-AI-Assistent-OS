@echo off
rem SEDRA - Freigaben der Klasse H ausserhalb des Browsers bestaetigen (SPEC_APPS_v1 G9).
rem   FREIGABE.bat liste              -> was auf deine Bestaetigung wartet (Text aus dem Kern)
rem   FREIGABE.bat freigeben B-XXXX   -> bestaetigen
rem   FREIGABE.bat ablehnen B-XXXX    -> ablehnen (die Entscheidung bleibt offen)
rem SEDRA muss laufen. Pfade und Python wie START_SEDRA.bat.
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
  echo Aufruf: FREIGABE.bat liste ^| freigeben B-XXXX ^| ablehnen B-XXXX
  exit /b 2
)
cd /d "%RT%"
"%PY%" %PYFLAGS% -m sedra_runtime.desk.freigabe_konsole --root "%PROJ%" %*
exit /b %ERRORLEVEL%
