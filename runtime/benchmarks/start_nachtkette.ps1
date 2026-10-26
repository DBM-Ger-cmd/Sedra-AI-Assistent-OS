# Starter der Nachtkette aus A1 (U2-11b). Wird von der geplanten Aufgabe 'SEDRA Nachtkette A1 2026-10-26' bei der Anmeldung gerufen.
#   start_nachtkette.ps1 -Bis 2026-11-30            startet benchmarks\night_chain.py unsichtbar, falls es nicht schon laeuft
#   start_nachtkette.ps1 -Bis 2026-11-30 -Trocken   zeigt nur, was die Kette taete (Freigabe, Fenster, Auftraege, RAM, Lease); startet nichts
# Pfade kommen aus der Lage dieses Skripts: <A1>\runtime\benchmarks -> Projekt <A1>\workspace\GUPPI_OS, Python <A1>\runtime\.venv.
# Die Kette startet nur mit Freigabedatei local_config\nacht_frei.txt, nur im Zeitfenster und nur bis zum Enddatum (-Bis).
param(
    [Parameter(Mandatory = $true)][string]$Bis,
    [switch]$Trocken,
    [int]$StartStunde = 22,
    [int]$StopStunde = 7
)
$ErrorActionPreference = 'Stop'
$runtime = Split-Path -Parent $PSScriptRoot
$a1 = Split-Path -Parent $runtime
$project = Join-Path $a1 'workspace\GUPPI_OS'
$python = Join-Path $runtime '.venv\Scripts\python.exe'
$script = Join-Path $PSScriptRoot 'night_chain.py'
foreach ($p in @($python, $script, $project)) {
    if (-not (Test-Path -LiteralPath $p)) { Write-Output "FEHLT: $p"; exit 2 }
}
$common = @('--bis', $Bis, '--start-hour', $StartStunde, '--stop-hour', $StopStunde)
if ($Trocken) {
    $env:PYTHONIOENCODING = 'utf-8'
    & $python -B $script $project @common --dry-run
    exit $LASTEXITCODE
}
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*night_chain.py*' }
if ($running) { exit 0 }
$env:PYTHONIOENCODING = 'utf-8'
$argList = '-B "' + $script + '" "' + $project + '" --bis ' + $Bis + ' --start-hour ' + $StartStunde + ' --stop-hour ' + $StopStunde
Start-Process -FilePath $python -ArgumentList $argList -WorkingDirectory $runtime -WindowStyle Hidden
exit 0
