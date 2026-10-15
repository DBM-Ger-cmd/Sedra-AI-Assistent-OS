@echo off
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -File "%~dp0runtime\Ersteinrichtung.ps1"
if errorlevel 1 (
 echo Einrichtung nicht abgeschlossen. Siehe docs/BETRIEB.md (Abschnitt Einrichtung).
 pause
 exit /b 1
)
call "%~dp0START_GUPPI.bat"
