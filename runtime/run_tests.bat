@echo off
setlocal
rem The venv's python.exe is called directly: activate.bat holds the folder the venv was created in, and after the
rem package folder was moved it pointed elsewhere, so the system Python without PyYAML ran (review 2026-10-11).
rem src: the package also runs without "pip install -e ."; tests: shared helpers such as host_isolation.py
set "PYTHONPATH=%~dp0src;%~dp0tests;%PYTHONPATH%"
"%~dp0.venv\Scripts\python.exe" -m unittest discover -s "%~dp0tests" -t "%~dp0tests" -v
