@echo off
rem Einheitlicher Erststart + Start. Funktioniert auch in Ordnern mit Klammern im Namen, z.B. "(1)".
rem Bleibt immer offen und schreibt ein Protokoll nach runtime\einrichtung.log.
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "RT=%ROOT%\runtime"
set "LOG=%RT%\einrichtung.log"
set "GUPPI_PROJECT=%ROOT%\workspace\GUPPI_OS"
set "ARCH=%ROOT%\architecture\GUPPI_Architecture_v1.20_SELF_DEVELOPMENT"
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

echo GUPPI Einrichtung und Start
echo Ordner: %ROOT%
echo Protokoll: %LOG%
echo.
echo %DATE% %TIME% Start > "%LOG%"

if not exist "%GUPPI_PROJECT%" mkdir "%GUPPI_PROJECT%"
if exist "%RT%\portable\python\current\python.exe" goto :start

echo Portable Python fehlt, Ersteinrichtung laeuft.
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%RT%\Ersteinrichtung.ps1"
if errorlevel 1 goto :fail
if not exist "%RT%\portable\python\current\python.exe" goto :fail

:start
echo.
"%RT%\portable\python\current\python.exe" -I -B "%RT%\benchmarks\engine_download.py"
if errorlevel 1 goto :fail
if not exist "%RT%\config\local_paths.yaml" (
 "%PS%" -NoProfile -ExecutionPolicy Bypass -File "%RT%\Erststart_Konfig.ps1"
 if errorlevel 1 goto :fail
)
echo Pruefe Laufzeit ...
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%RT%\Test-PortableRuntime.ps1"
if errorlevel 1 goto :fail
echo Starte GUPPI ...
cd /d "%RT%"
"%RT%\portable\python\current\python.exe" -I -B -m guppi_runtime.uix_start --root "%GUPPI_PROJECT%" --architecture "%ARCH%" %*
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo FEHLER: Einrichtung oder Start nicht abgeschlossen. Siehe oben und docs\BETRIEB.md.
echo %DATE% %TIME% Fehler >> "%LOG%"
pause
exit /b 1
