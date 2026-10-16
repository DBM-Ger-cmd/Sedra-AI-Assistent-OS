# Packet capture for the sandbox boundary finding "port 53 reachable" (PC-03 evidence "network capture").
# Run ONCE in an ADMINISTRATOR PowerShell from the runtime folder:
#
#     powershell -ExecutionPolicy Bypass -File benchmarks\sandbox_dns_capture.ps1
#
# What it does: records only port-53 traffic on all host adapters with Windows' built-in pktmon, runs the boundary check (the
# guest queries a unique random name such as gp<random>.guppi-boundary.example.com via UDP and TCP to 1.1.1.1, 8.8.8.8 and
# 9.9.9.9), stops the capture and searches it for that name. Found = a query left the host. Not found = no query left.
# It changes no setting permanently: the pktmon filter is removed at the end. Output: runtime_data\acceptance\dns_capture_<time>.*
$ErrorActionPreference = "Stop"
$runtime = Split-Path -Parent $PSScriptRoot
$project = Join-Path (Split-Path -Parent $runtime) "workspace\GUPPI_OS"
$outDir = Join-Path $project "runtime_data\acceptance"
New-Item -ItemType Directory -Force $outDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$etl = Join-Path $outDir "dns_capture_$stamp.etl"
$pcap = Join-Path $outDir "dns_capture_$stamp.pcapng"
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "Bitte in einer Administrator-PowerShell starten (pktmon braucht Adminrechte)." }

# pktmon writes harmless notes ("not running") to stderr; in Windows PowerShell 5.1 that would abort the script, so native calls
# run with "Continue" and only a failed start counts.
$ErrorActionPreference = "Continue"
cmd /c "pktmon stop >nul 2>&1"
cmd /c "pktmon filter remove >nul 2>&1"
cmd /c "pktmon filter add GUPPI-DNS -p 53 >nul 2>&1"
cmd /c "pktmon start --capture --pkt-size 0 --file-name `"$etl`" >nul 2>&1"
if ($LASTEXITCODE -ne 0) { throw "pktmon konnte den Mitschnitt nicht starten (Exit-Code $LASTEXITCODE)." }
try {
    Set-Location $runtime
    $env:PYTHONPATH = "src"
    $check = & .\.venv\Scripts\python.exe benchmarks\sandbox_boundary_check.py $project 2>&1 | Out-String
} finally {
    cmd /c "pktmon stop >nul 2>&1"
    cmd /c "pktmon filter remove >nul 2>&1"
}
cmd /c "pktmon etl2pcap `"$etl`" --out `"$pcap`" >nul 2>&1"
if (-not (Test-Path $pcap)) { throw "Umwandlung des Mitschnitts fehlgeschlagen: $etl" }

$name = ([regex]::Match($check, '"dns_probe_name":\s*"([^"]+)"')).Groups[1].Value
if (-not $name) { Write-Output $check; throw "Grenztest hat keinen DNS-Namen geliefert (VM-Start gescheitert?). Bitte erneut starten." }
$label = ($name -split '\.')[0]                     # the random first label, as it appears in a DNS packet
$bytes = [IO.File]::ReadAllBytes($pcap)
$text = [Text.Encoding]::ASCII.GetString($bytes)
$hits = ([regex]::Matches($text, [regex]::Escape($label))).Count
$result = [ordered]@{
    schema = 1; kind = "sandbox_dns_capture"; created_at = $stamp; dns_probe_name = $name
    capture_file = $pcap; capture_bytes = $bytes.Length; probe_name_hits_in_capture = $hits
    verdict = $(if ($hits -eq 0) { "NO_QUERY_LEFT_THE_HOST" } else { "QUERY_LEFT_THE_HOST" })
    boundary_check_output = $check.Trim()
}
$json = Join-Path $outDir "dns_capture_$stamp.json"
$result | ConvertTo-Json -Depth 4 | Set-Content $json -Encoding UTF8
Write-Output ""
Write-Output "DNS-Name des Gastes : $name"
Write-Output "Treffer im Mitschnitt: $hits"
Write-Output "Ergebnis            : $($result.verdict)"
Write-Output "Bericht             : $json"
