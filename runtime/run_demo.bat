@echo off
setlocal
rem The venv python is called directly; activate.bat and the "guppi" launcher hold the folder the venv was created in.
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
"%~dp0.venv\Scripts\python.exe" -m guppi_runtime demo --intent "Create a GUPPI runtime demo artifact"
