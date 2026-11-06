@echo off
setlocal
rem The venv python is called directly; activate.bat and the "sedra" launcher hold the folder the venv was created in.
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
"%~dp0.venv\Scripts\python.exe" -m sedra_runtime demo --intent "Create a SEDRA runtime demo artifact"
