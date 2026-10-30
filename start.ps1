<#
.SYNOPSIS
  Sets up (once) and starts everything needed for iso-diagram.

.DESCRIPTION
  1. creates a local virtualenv in .\.venv and pip-installs requirements.txt
  2. downloads third-party assets into .\assets (three.js + Isopacks/Kubernetes icons) if missing
  3. renders every examples\*.iso.yaml into .\out as a smoke test
  4. starts the local service (python -m isodiagram serve) in the background on http://127.0.0.1:<Port>/

  Stop it again with .\stop.ps1.  Convert a file with .\render.ps1 <file.iso.yaml> [-Png].

.PARAMETER Port       Port for the local service (default 8765).
.PARAMETER Reinstall  Recreate the virtualenv and re-download assets.
.PARAMETER NoServer   Only set up + smoke test, do not start the service.
.PARAMETER Open       Open the service in the default browser when it is up.
#>
[CmdletBinding()]
param(
    [int]$Port = 8765,
    [switch]$Reinstall,
    [switch]$NoServer,
    [switch]$Open
)
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
Set-Location $Root
$Venv = Join-Path $Root '.venv'
$Py   = Join-Path $Venv 'Scripts\python.exe'
$OutDir = Join-Path $Root 'out'
New-Item -ItemType Directory -Force $OutDir | Out-Null

function Step($m) { Write-Host "==> $m" -ForegroundColor Cyan }

# --- 1. python + venv ---------------------------------------------------------------------------
if ($Reinstall -and (Test-Path $Venv)) { Step 'Removing existing virtualenv'; Remove-Item $Venv -Recurse -Force }
if (-not (Test-Path $Py)) {
    Step 'Creating virtualenv (.venv)'
    $sysPy = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $sysPy) { $sysPy = (Get-Command py -ErrorAction SilentlyContinue).Source }
    if (-not $sysPy) { throw 'Python 3.10+ was not found on PATH.' }
    & $sysPy -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtualenv.' }
}
$stamp = Join-Path $Venv '.requirements.stamp'
$reqHash = (Get-FileHash (Join-Path $Root 'requirements.txt') -Algorithm SHA256).Hash
if (-not (Test-Path $stamp) -or (Get-Content $stamp -Raw).Trim() -ne $reqHash) {
    Step 'Installing Python dependencies (pip)'
    & $Py -m pip install --disable-pip-version-check -q -r (Join-Path $Root 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'pip install failed.' }
    Set-Content $stamp $reqHash
} else { Step 'Python dependencies up to date' }

# --- 2. assets ----------------------------------------------------------------------------------
if ($Reinstall) { Remove-Item (Join-Path $Root 'assets') -Recurse -Force -ErrorAction SilentlyContinue }
Step 'Fetching assets (three.js, icon packs) if missing'
& $Py (Join-Path $Root 'tools\fetch_assets.py')
if ($LASTEXITCODE -ne 0) { throw 'Asset download failed (check network / proxy).' }

# --- 3. smoke test ------------------------------------------------------------------------------
Step 'Rendering examples (HTML)'
Get-ChildItem (Join-Path $Root 'examples') -Filter '*.iso.yaml' | ForEach-Object {
    & $Py -m isodiagram render $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "Render failed for $($_.Name)" }
}

if ($NoServer) { Write-Host "`nSetup complete. Convert a file with .\render.ps1 examples\llm-platform.iso.yaml -Png" -ForegroundColor Green; return }

# --- 4. service ---------------------------------------------------------------------------------
$PidFile = Join-Path $OutDir 'server.pid'
if (Test-Path $PidFile) {
    $old = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) {
        Step "Stopping previous service (PID $old)"
        Stop-Process -Id $old -Force
    }
    Remove-Item $PidFile -Force
}
Step "Starting service on port $Port"
$log = Join-Path $OutDir 'server.log'
$proc = Start-Process -FilePath $Py -ArgumentList @('-m', 'isodiagram', 'serve', '--port', $Port) `
    -WorkingDirectory $Root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $log -RedirectStandardError (Join-Path $OutDir 'server.err.log')
Set-Content $PidFile $proc.Id

$url = "http://127.0.0.1:$Port/"
$up = $false
foreach ($i in 1..30) {
    Start-Sleep -Milliseconds 300
    try { if ((Invoke-WebRequest "${url}health" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { $up = $true; break } } catch { }
}
if (-not $up) { throw "Service did not come up. See $log and out\server.err.log" }

Write-Host ""
Write-Host "iso-diagram is running (PID $($proc.Id)): $url" -ForegroundColor Green
Write-Host "  Convert a file : .\render.ps1 examples\llm-platform.iso.yaml -Png"
Write-Host "  Stop service   : .\stop.ps1"
if ($Open) { Start-Process $url }
