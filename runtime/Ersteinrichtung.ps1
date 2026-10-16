$ErrorActionPreference = 'Stop'
if (![Environment]::Is64BitOperatingSystem) { throw 'Windows x64 erforderlich.' }
$Current = Join-Path $PSScriptRoot 'portable\python\current'
if (Test-Path -LiteralPath $Current) { & (Join-Path $PSScriptRoot 'Test-PortableRuntime.ps1'); exit }
$Assets = Join-Path $PSScriptRoot 'portable\downloads'
New-Item -ItemType Directory -Force -Path $Assets | Out-Null
$Records = @(
 @{file='python-3.14.8-embed-amd64.zip'; sha256='a93abe456ab01bd96d7a085b3cdb6566b3063f4241360d114142fbdb07f0a310'; url='https://www.python.org/ftp/python/3.14.8/python-3.14.8-embed-amd64.zip'},
 @{file='pyyaml-6.0.3-cp314-cp314-win_amd64.whl'; sha256='4a2e8cebe2ff6ab7d1050ecd59c25d4c8bd7e6f400f5f82b96557ac0abafd0ac'; url='https://files.pythonhosted.org/packages/23/20/bb6982b26a40bb43951265ba29d4c246ef0ff59c9fdcdf0ed04e0687de4d/pyyaml-6.0.3-cp314-cp314-win_amd64.whl'}
)
$Missing = @($Records | Where-Object { !(Test-Path -LiteralPath (Join-Path $Assets $_.file)) })
if ($Missing.Count -gt 0) {
 Write-Host 'Ersteinrichtung: portable Python- und PyYAML-Dateien von python.org / files.pythonhosted.org laden (ca. 13 MB).'
 Write-Host 'Keine globale Installation. Keine Modelle oder Gastimages werden heruntergeladen.'
 if ((Read-Host 'Zum Download JA eingeben; sonst abbrechen') -cne 'JA') { throw 'Ersteinrichtung abgebrochen. Offline-Dateien in runtime\portable\downloads ablegen.' }
}
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
foreach ($Record in $Records) {
 $Path = Join-Path $Assets $Record.file
 if (!(Test-Path -LiteralPath $Path)) { Invoke-WebRequest -UseBasicParsing -Uri $Record.url -OutFile $Path -TimeoutSec 120 }
 if ((Get-Item -LiteralPath $Path).Length -gt 32MB -or (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Record.sha256) { throw "Download-Pruefsumme stimmt nicht: $($Record.file)" }
}
$Manifest = @{schema=1;platform='windows-x64';python_version='3.14.8';python=@{file=$Records[0].file;sha256=$Records[0].sha256};pyyaml=@{file=$Records[1].file;sha256=$Records[1].sha256}}
$ManifestPath=Join-Path $Assets 'bundle.json'
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath $ManifestPath
$Bootstrap=Join-Path $Assets ('bootstrap-'+[guid]::NewGuid().ToString('N'))
try {
 # Only the checksum-verified official embedded archive is expanded for bootstrap.
 Expand-Archive -LiteralPath (Join-Path $Assets $Records[0].file) -DestinationPath $Bootstrap
 & (Join-Path $Bootstrap 'python.exe') -I -B (Join-Path $PSScriptRoot 'build_offline_runtime.py') --manifest $ManifestPath
 if ($LASTEXITCODE -ne 0) { throw 'Offline-Paketierung fehlgeschlagen.' }
 & (Join-Path $PSScriptRoot 'Test-PortableRuntime.ps1')
} finally { if (Test-Path -LiteralPath $Bootstrap) { Remove-Item -LiteralPath $Bootstrap -Recurse -Force } }
Write-Host 'Portable Umgebung eingerichtet. Echte Windows-/SDK-/VM-Abnahme bleibt erforderlich.'
