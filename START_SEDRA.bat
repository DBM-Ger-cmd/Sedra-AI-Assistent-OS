@echo off
rem DER Start von SEDRA: ein eigenes Fenster (Edge/Chrome App-Modus). Fenster schliessen = Server und Modell beenden.
rem   START_SEDRA.bat             -> die Uebersicht der Oberflaechen (Start) - auch wenn in uix.yaml schon eine gewaehlt ist
rem   START_SEDRA.bat cockpit     -> direkt in diese Oberflaeche (nur fuer diesen Start; die Wahl in uix.yaml bleibt)
rem   START_SEDRA.bat --gewaehlt  -> in die in uix.yaml gewaehlte Oberflaeche (wie "Diese Oberflaeche nehmen")
rem   START_SEDRA.bat --replace   -> einen noch laufenden SEDRA (auch aus einem alten Paket) vorher beenden
rem Laeuft schon ein SEDRA, startet kein zweiter: die Konsole nennt PID und Ordner des laufenden.
setlocal
set "SHELLARG=--uebersicht"
set "REST="
:args
if "%~1"=="" goto run
if "%~1"=="--gewaehlt" ( set "SHELLARG=" ) else if "%~1"=="--uebersicht" ( set "SHELLARG=--uebersicht" ) else (
 set "FIRST=%~1"
 setlocal enabledelayedexpansion
 if "!FIRST:~0,2!"=="--" ( endlocal & set "REST=%REST% %~1" ) else ( endlocal & set "SHELLARG=--shell %~1" )
)
shift
goto args
:run
cd /d "%~dp0runtime"
set "GUPPI_PROJECT=%~dp0workspace\GUPPI_OS"
if not exist "%GUPPI_PROJECT%" mkdir "%GUPPI_PROJECT%"
if exist "portable\python\current\python.exe" (
 "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -File "%~dp0runtime\Test-PortableRuntime.ps1"
 if errorlevel 1 exit /b 1
 "portable\python\current\python.exe" -I -B -m guppi_runtime.uix_start --root "%GUPPI_PROJECT%" --architecture "%~dp0architecture\GUPPI_Architecture_v1.20_SELF_DEVELOPMENT" %SHELLARG% %REST%
 if errorlevel 1 pause
 exit /b
)
if exist ".venv\Scripts\python.exe" (
 set "PYTHONPATH=%CD%\src"
 ".venv\Scripts\python.exe" -B -m guppi_runtime.uix_start --root "%GUPPI_PROJECT%" --architecture "%~dp0architecture\GUPPI_Architecture_v1.20_SELF_DEVELOPMENT" %SHELLARG% %REST%
 if errorlevel 1 pause
 exit /b
)
echo Python-Umgebung fehlt. Zuerst ERSTER_START.bat ausfuehren.
pause
exit /b 2
