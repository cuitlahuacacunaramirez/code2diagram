<#
.SYNOPSIS  Stops the background iso-diagram service started by start.ps1.
#>
$PidFile = Join-Path $PSScriptRoot 'out\server.pid'
if (-not (Test-Path $PidFile)) { Write-Host 'No service PID file found - nothing to stop.'; return }
$id = Get-Content $PidFile
if ($id -and (Get-Process -Id $id -ErrorAction SilentlyContinue)) {
    Stop-Process -Id $id -Force
    Write-Host "Stopped iso-diagram service (PID $id)."
} else {
    Write-Host 'Service was not running.'
}
Remove-Item $PidFile -Force
