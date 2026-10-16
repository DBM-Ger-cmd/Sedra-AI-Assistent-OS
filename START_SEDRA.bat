@echo off
rem SEDRA - der eine Start. Ersetzt ERSTER_START.bat, START_GUPPI.bat und GUPPI_EINRICHTEN_UND_STARTEN.bat.
rem   START_SEDRA.bat             -> richtet nur ein, was fehlt, und fragt, welche Oberflaeche starten soll
rem   START_SEDRA.bat cockpit     -> direkt in diese Oberflaeche (nur fuer diesen Start; die Wahl in uix.yaml bleibt)
rem   START_SEDRA.bat --uebersicht -> die Uebersicht aller Oberflaechen
rem   START_SEDRA.bat --gewaehlt  -> in die in uix.yaml gewaehlte Oberflaeche, ohne Frage
rem   START_SEDRA.bat --replace   -> einen noch laufenden SEDRA (auch aus einem alten Paket) vorher beenden
rem Fenster schliessen = Server und Modell beenden. Protokoll: runtime\einrichtung.log
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "RT=%ROOT%\runtime"
set "LOG=%RT%\einrichtung.log"
set "PROJ=%ROOT%\workspace\GUPPI_OS"
set "ARCH=%ROOT%\architecture\GUPPI_Architecture_v1.20_SELF_DEVELOPMENT"
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "PY=%RT%\portable\python\current\python.exe"
set "PYFLAGS=-I -B"
set "SHELLARG="
set "REST="
set "GEWAEHLT=0"

:args
if "%~1"=="" goto :start
if /i "%~1"=="--gewaehlt" goto :arg_gewaehlt
if /i "%~1"=="--uebersicht" goto :arg_uebersicht
if /i "%~1"=="--replace" goto :arg_replace
set "SHELLARG=--shell %~1"
set "GEWAEHLT=1"
shift
goto :args

:arg_gewaehlt
set "SHELLARG="
set "GEWAEHLT=1"
shift
goto :args

:arg_uebersicht
set "SHELLARG=--uebersicht"
set "GEWAEHLT=1"
shift
goto :args

:arg_replace
set "REST=%REST% --replace"
shift
goto :args

:start
if not exist "%PROJ%" mkdir "%PROJ%"
echo SEDRA
echo Ordner: %ROOT%
echo %DATE% %TIME% Start >> "%LOG%"
if exist "%PY%" goto :pruefen
if exist "%RT%\.venv\Scripts\python.exe" goto :entwickler
echo Die Python-Umgebung fehlt. Die Ersteinrichtung startet (sie fragt vor Downloads).
if not exist "%RT%\portable\sandbox\RELEASE_LOCK.json" (
  echo Hinweis: runtime\portable\sandbox fehlt - SEDRA wird ohne Sandbox-SDK eingerichtet.
  echo          Das SDK braucht nur die DevVM ^(Selbstentwicklung^); Ordner spaeter kopieren, dann
  echo          runtime\portable\python loeschen und START_SEDRA.bat erneut starten.
  echo %DATE% %TIME% Hinweis: ohne Sandbox-SDK >> "%LOG%"
)
goto :einrichten

:einrichten
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%RT%\Ersteinrichtung.ps1"
if errorlevel 1 goto :fail
if not exist "%PY%" goto :fail
goto :pruefen


:entwickler
rem Entwicklerpfad: eine vorhandene runtime\.venv, ohne portables Python.
set "PY=%RT%\.venv\Scripts\python.exe"
set "PYFLAGS=-B"
set "PYTHONPATH=%RT%\src"
goto :wahl

:pruefen
echo Engine pruefen ...
"%PY%" %PYFLAGS% "%RT%\benchmarks\engine_download.py"
if errorlevel 1 (
  echo Hinweis: Die llama.cpp-Engine fehlt oder konnte nicht geladen werden. Die Oberflaeche startet trotzdem;
  echo          ohne Engine antwortet kein Modell. Siehe docs\BETRIEB.md ^(Engine^).
  echo %DATE% %TIME% Hinweis: Engine fehlt >> "%LOG%"
)
if not exist "%RT%\config\local_paths.yaml" "%PS%" -NoProfile -ExecutionPolicy Bypass -File "%RT%\Erststart_Konfig.ps1"
if errorlevel 1 goto :fail
echo Laufzeit pruefen ...
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%RT%\Test-PortableRuntime.ps1"
if errorlevel 1 goto :fail
goto :wahl

:wahl
if "%GEWAEHLT%"=="1" goto :starten
goto :menue

:menue
cd /d "%RT%"
set "N=0"
echo.
echo Welche Oberflaeche soll starten?
echo   0  Uebersicht aller Oberflaechen
for /f "usebackq tokens=1,* delims=|" %%a in (`"%PY%" %PYFLAGS% -m guppi_runtime.uix_start --liste`) do call :zeile "%%a" "%%b"
echo.
set "CHOICE="
set /p "CHOICE=Nummer eingeben (Enter = Standard, die Oberflaeche aus uix.yaml): "
if "%CHOICE%"=="" goto :menue_gewaehlt
if "%CHOICE%"=="0" goto :menue_uebersicht
if /i "%CHOICE:~0,1%"=="s" goto :menue_standard
echo %CHOICE%| findstr /r "^[0-9][0-9]*$" >nul || goto :menue_falsch
if %CHOICE% GTR %N% goto :menue_falsch
call set "SEL=%%ID%CHOICE%%%"
set "SHELLARG=--shell %SEL%"
goto :starten

:menue_gewaehlt
set "SHELLARG="
goto :starten

:menue_uebersicht
set "SHELLARG=--uebersicht"
goto :starten

:menue_falsch
echo Keine gueltige Nummer. Bitte erneut waehlen.
goto :menue

:zeile
set /a N+=1
set "ID%N%=%~1"
echo   %N%  %~2
echo        s%N%  zum Standard machen (dann startet diese Oberflaeche)
goto :eof

:menue_standard
set "STD=%CHOICE:~1%"
echo %STD%| findstr /r "^[0-9][0-9]*$" >nul || goto :menue_falsch
if %STD% GTR %N% goto :menue_falsch
if %STD% LSS 1 goto :menue_falsch
call set "SEL=%%ID%STD%%%"
"%PY%" %PYFLAGS% -m guppi_runtime.uix_start --root "%PROJ%" --architecture "%ARCH%" --als-standard %SEL% || goto :menue_falsch
set "SHELLARG="
goto :starten

:starten
echo SEDRA startet ...
cd /d "%RT%"
"%PY%" %PYFLAGS% -m guppi_runtime.uix_start --root "%PROJ%" --architecture "%ARCH%" %SHELLARG% %REST%
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo FEHLER: Einrichtung oder Start nicht abgeschlossen. Siehe oben und das Protokoll: %LOG%
echo %DATE% %TIME% Fehler >> "%LOG%"
pause
exit /b 1
