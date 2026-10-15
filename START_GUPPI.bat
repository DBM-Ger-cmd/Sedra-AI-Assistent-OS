@echo off
rem START_GUPPI.bat ist der alte Name. Der Start heisst START_SEDRA.bat - mit Uebersicht der Oberflaechen, oder START_SEDRA.bat <shell>.
rem Diese Datei leitet nur weiter (gleiche Optionen), damit alte Verknuepfungen weiter funktionieren.
echo Hinweis: der Start heisst jetzt START_SEDRA.bat (Uebersicht) bzw. START_SEDRA.bat ^<oberflaeche^>. Weiter mit START_SEDRA ...
call "%~dp0START_SEDRA.bat" %*
