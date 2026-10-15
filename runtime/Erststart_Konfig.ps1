# Erststart-Konfiguration: fragt den Modellordner dieses PCs, schreibt die Schalter mit den Standardwerten und prüft die Engine.
# Läuft nach Ersteinrichtung.ps1 (aufgerufen von GUPPI_EINRICHTEN_UND_STARTEN.bat). Nichts wird heruntergeladen.
$ErrorActionPreference = 'Stop'
$Rt = $PSScriptRoot
$Root = Split-Path -Parent $Rt
$Py = Join-Path $Rt 'portable\python\current\python.exe'
$Cfg = Join-Path $Rt 'config\local_paths.yaml'
$LocalCfg = Join-Path $Root 'workspace\GUPPI_OS\local_config'
New-Item -ItemType Directory -Force -Path $LocalCfg | Out-Null

if (!(Test-Path -LiteralPath $Cfg)) {
 $Default = Join-Path $env:USERPROFILE 'GUPPI\Modelle'
 Write-Host ''
 Write-Host 'Modellordner: hier liegen die GGUF-Modelldateien (.gguf). Ein Modell wird dadurch nicht geladen.'
 $Answer = Read-Host "Modellordner eingeben [Enter = $Default]"
 $Models = if ([string]::IsNullOrWhiteSpace($Answer)) { $Default } else { $Answer.Trim().Trim('"') }
 New-Item -ItemType Directory -Force -Path $Models | Out-Null
 $Lines = @('# Ordner dieses PCs (nicht in git). Geschrieben von der Erststart-Konfiguration.', 'local_paths:', "  modelle: '$Models'")
 Set-Content -LiteralPath $Cfg -Value $Lines -Encoding UTF8
 Write-Host "Modellordner gesetzt: $Models"
}

$Sw = Join-Path $LocalCfg 'switches.yaml'
if (!(Test-Path -LiteralPath $Sw)) {
 Set-Content -LiteralPath $Sw -Encoding UTF8 -Value @(
  '# Schalter dieses PCs. Erststart-Standard: automatisches Laden und eigener llama-server an, MTP aus (siehe docs/BETRIEB.md).',
  'switches:',
  '  model_loader: {enabled: true}',
  '  llama_server: {enabled: true, mtp: false}')
 Write-Host 'Schalter gesetzt: automatisches Laden an, eigener llama-server an, MTP aus.'
}

$Build = (Select-String -LiteralPath (Join-Path $Rt 'config\llama_server.yaml') -Pattern '^\s*engine_build:\s*(\S+)').Matches[0].Groups[1].Value
$Engine = Join-Path $Root 'engines'
$Check = & $Py -I -B -c "import sys; from pathlib import Path; from guppi_runtime.models import engine_provision as e; print(e.verify_engine(Path(sys.argv[1]), sys.argv[2]))" $Engine $Build
Write-Host "Engine $Build geprüft: $Check"
if ($Check -notmatch "^\(True") { throw "Engine $Build fehlt oder ist verändert (engines\llama.cpp\$Build). Erststart erneut starten; die Engine wird dann geladen." }
