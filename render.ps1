<#
.SYNOPSIS
  Converts an *.iso.yaml file into an interactive HTML diagram and optionally a PNG.

.EXAMPLE
  .\render.ps1 examples\llm-platform.iso.yaml
  .\render.ps1 examples\llm-platform.iso.yaml -Png -Open
  .\render.ps1 my.iso.yaml -Png -Size 2560x1440 -Scale 1 -OutDir C:\temp\diagrams
  .\render.ps1 my.iso.yaml -ValidateOnly
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory, Position = 0)][string]$Path,
    [switch]$Png,
    [string]$Size = '1920x1080',
    [double]$Scale = 1,
    [string]$OutDir,
    [switch]$ValidateOnly,
    [switch]$Open
)
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Py = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Py)) { throw 'Not set up yet - run .\start.ps1 -NoServer first.' }
if (-not (Test-Path $Path)) { throw "Input file not found: $Path" }
$Path = (Resolve-Path $Path).Path
Set-Location $Root

if ($ValidateOnly) { & $Py -m isodiagram validate $Path; exit $LASTEXITCODE }

$name = (Split-Path $Path -Leaf) -replace '\.iso\.ya?ml$', '' -replace '\.ya?ml$', ''
$dir = if ($OutDir) { New-Item -ItemType Directory -Force $OutDir | Select-Object -ExpandProperty FullName } else { Join-Path $Root 'out' }
$html = Join-Path $dir "$name.html"
$argv = @('-m', 'isodiagram', 'render', $Path, '-o', $html)
if ($Png) { $argv += @('--png', (Join-Path $dir "$name.png"), '--size', $Size, '--scale', $Scale) }
& $Py @argv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($Open) { Start-Process $(if ($Png) { Join-Path $dir "$name.png" } else { $html }) }
