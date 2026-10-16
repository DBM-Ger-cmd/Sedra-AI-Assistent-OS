@echo off
setlocal
cd /d "%~dp0"
if not exist .venv python -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" prepare_sandbox.py --install
if errorlevel 1 exit /b 1
echo GUPPI runtime and integrated sandbox SDK installed. PC acceptance is pending.
