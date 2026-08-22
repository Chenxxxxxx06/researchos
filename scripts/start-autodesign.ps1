param(
  [int]$Port = 8010,
  [switch]$SkipBrowserSetup
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$autoDesignRoot = Join-Path $repoRoot 'integrations\AutoDesign'
$stateRoot = Join-Path $repoRoot 'data\autodesign'
$browserMarker = Join-Path $stateRoot 'browser-ready'

Set-Location $repoRoot
if (-not (Test-Path (Join-Path $autoDesignRoot 'pyproject.toml'))) {
  Write-Host 'Initializing AutoDesign submodule...'
  git submodule update --init --depth 1 integrations/AutoDesign
  if ($LASTEXITCODE -ne 0) { throw 'Unable to initialize AutoDesign.' }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw 'uv is required. Install it from https://docs.astral.sh/uv/ and retry.'
}

New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
Set-Location $autoDesignRoot
Write-Host 'Synchronizing AutoDesign Python dependencies...'
uv sync
if ($LASTEXITCODE -ne 0) { throw 'AutoDesign dependency installation failed.' }

if (-not $SkipBrowserSetup -and -not (Test-Path $browserMarker)) {
  Write-Host 'Installing the Chromium renderer used by editable artifacts...'
  uv run python scripts/install_playwright_browsers.py
  if ($LASTEXITCODE -ne 0) { throw 'AutoDesign browser setup failed.' }
  Set-Content -Path $browserMarker -Value (Get-Date -Format o)
}

Write-Host "AutoDesign is starting at http://localhost:$Port"
Write-Host 'Generated files will be stored under integrations/AutoDesign/out/runs/<run_id>/final.'
uv run uvicorn scripts.web_server:app --host 0.0.0.0 --port $Port
exit $LASTEXITCODE
