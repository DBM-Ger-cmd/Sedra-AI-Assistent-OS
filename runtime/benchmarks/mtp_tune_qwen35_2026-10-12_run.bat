@echo off
rem Captain 2026-10-12: repoint + tune coder.llama_qwen35 (Q6 with MTP head). Speed first (waits for the GPU lease), then the context ladder.
set GUPPI_ENGINE_BUILD=b11160
set TESTLAB_OWNER=claude_mtp_tune
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
".venv\Scripts\python.exe" benchmarks\mtp_tune_qwen35_2026-10-12.py "%~dp0..\..\workspace\GUPPI_OS" > "%~dp0..\..\workspace\GUPPI_OS\runtime_data\measurements\mtp_tune_qwen35_2026-10-12.log" 2>&1
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" benchmarks\context_ladder.py "%~dp0..\..\workspace\GUPPI_OS" coder.llama_qwen35 --max 131072 --probes 2 --from 16384 --tag mtp_q6 > "%~dp0..\..\workspace\GUPPI_OS\runtime_data\measurements\ladder_mtp_q6_2026-10-12.log" 2>&1
