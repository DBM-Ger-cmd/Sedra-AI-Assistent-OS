$ErrorActionPreference = 'Stop'
$Root = Join-Path $PSScriptRoot 'portable\python\current'
$ReceiptPath = Join-Path $Root 'bundle-receipt.json'
if (!(Test-Path -LiteralPath $ReceiptPath -PathType Leaf)) { throw 'Portable Python fehlt. Offline-Paket zuerst auf dem Build-Rechner bereitstellen.' }
$Receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
if ($Receipt.schema -ne 1 -or $Receipt.platform -ne 'windows-x64' -or ($Receipt.sdk_version -ne '0.7.4' -and $Receipt.sdk_version -ne 'none')) { throw 'Ungueltiges Python-Paket.' }
if ($Receipt.sdk_version -eq 'none') { Write-Output 'Hinweis: Python-Paket ohne Sandbox-SDK (nur fuer die DevVM noetig).' }
if (![Environment]::Is64BitOperatingSystem) { throw 'Windows x64 erforderlich.' }
if ((Get-Item -LiteralPath $Root).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Verknuepfung als Paketwurzel.' }
$Seen = @{}
foreach ($File in $Receipt.files) {
    if ($File.path -match '(^/|\\|:|(^|/)\.\.?(/|$))' -or $Seen.ContainsKey($File.path)) { throw 'Ungueltiger Paketpfad.' }
    $Seen[$File.path] = $true
    $Path = Join-Path $Root $File.path
    $Part = Get-Item -LiteralPath $Path
    $Cursor = $Part
    while ($Cursor.FullName -ne (Get-Item -LiteralPath $Root).FullName) {
        if ($Cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Verknuepfung im Python-Paket.' }
        $Cursor = if ($Cursor -is [IO.DirectoryInfo]) { $Cursor.Parent } else { $Cursor.Directory }
        if ($null -eq $Cursor) { throw 'Paketpfad ausserhalb des Python-Pakets.' }
    }
    if ($Part.PSIsContainer -or $Part.Length -ne $File.bytes -or (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $File.sha256) { throw "Pruefsumme stimmt nicht: $($File.path)" }
}
$Files = @(Get-ChildItem -LiteralPath $Root -Recurse -File)
if ($Files.Count -ne ($Seen.Count + 1)) { throw 'Zusaetzliche Dateien im Python-Paket.' }
Write-Output 'Portable Python und lokale Pakete geprueft; PC-Abnahme weiterhin erforderlich.'
