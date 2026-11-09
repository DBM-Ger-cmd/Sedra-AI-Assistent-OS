@echo off
rem SEDRA - der eine Start. Ersetzt ERSTER_START.bat, START_SEDRA.bat und SEDRA_EINRICHTEN_UND_STARTEN.bat.
rem   START_SEDRA.bat             -> richtet nur ein, was fehlt, und startet gleich One Sedra (keine Auswahl;
rem                                  die anderen Oberflaechen waehlt man in den Menues der Oberflaeche)
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
set "PROJ=%ROOT%\workspace\SEDRA_OS"
set "ARCH=%ROOT%\architecture\SEDRA_Architecture_v1.20_SELF_DEVELOPMENT"
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "PY=%RT%\portable\python\current\python.exe"
set "PYFLAGS=-I -B -X utf8"
rem UTF-8 auch fuer Kindprozesse (z. B. whisper-ctranslate2 bricht in der cp1252-Konsole ab); -I ignoriert die Variable, darum zusaetzlich -X utf8
set "PYTHONUTF8=1"
set "SHELLARG="
set "REST="
set "GEWAEHLT=0"
set "EINSTIEG=harness"

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
rem Uebergang vom alten Ordnernamen (vor 1.23.0): der alte Name ist hier absichtlich zerlegt, damit er sonst nirgends im Programm vorkommt.
set "ALT=GUP"
set "ALT=%ALT%PI_OS"
if exist "%ROOT%\workspace\%ALT%" if not exist "%PROJ%" move "%ROOT%\workspace\%ALT%" "%PROJ%" >nul
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
set "PYFLAGS=-B -X utf8"
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
rem Ohne Auswahl: gleich in One Sedra (Captain 04.11.2026). Die anderen Oberflaechen waehlt man in den Menues der Oberflaeche.
if "%GEWAEHLT%"=="0" set "SHELLARG=--shell %EINSTIEG%"
goto :starten

:starten
echo SEDRA startet ...
cd /d "%RT%"
"%PY%" %PYFLAGS% -m sedra_runtime.umzug --root "%ROOT%" >> "%LOG%" 2>&1
"%PY%" %PYFLAGS% -m sedra_runtime.uix_start --root "%PROJ%" --architecture "%ARCH%" %SHELLARG% %REST%
if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo FEHLER: Einrichtung oder Start nicht abgeschlossen. Siehe oben und das Protokoll: %LOG%
echo %DATE% %TIME% Fehler >> "%LOG%"
pause
exit /b 1
