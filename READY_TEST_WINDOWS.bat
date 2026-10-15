@echo off
setlocal
cd /d "%~dp0runtime"
set "GUPPI_PROJECT=%~dp0workspace\GUPPI_OS"
if exist "portable\python\current\python.exe" (
 "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -File "%~dp0runtime\Test-PortableRuntime.ps1"
 if errorlevel 1 exit /b 1
 "portable\python\current\python.exe" -I -B -m guppi_runtime.pc_diagnose --root "%GUPPI_PROJECT%" --architecture "%~dp0architecture\GUPPI_Architecture_v1.20_SELF_DEVELOPMENT"
 pause
 exit /b
)
echo Zuerst ERSTER_START.bat ausfuehren.
pause
exit /b 2
