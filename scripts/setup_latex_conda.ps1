# Install and verify the Windows LaTeX toolchain used by the local ResearchOS API.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/setup_latex_conda.ps1
param(
    [string]$EnvironmentName = "researchos"
)

$ErrorActionPreference = "Stop"
$conda = Get-Command conda.exe -ErrorAction Stop
$environmentData = (& $conda.Source env list --json | ConvertFrom-Json)
$prefix = $environmentData.envs |
    Where-Object { (Split-Path $_ -Leaf) -eq $EnvironmentName } |
    Select-Object -First 1
if (-not $prefix) {
    throw "Conda environment '$EnvironmentName' does not exist."
}

Write-Host "==> Installing latexmk in $prefix" -ForegroundColor Cyan
& $conda.Source install -n $EnvironmentName --override-channels -c conda-forge "latexmk=4.88" -y
if ($LASTEXITCODE -ne 0) { throw "Conda latexmk installation failed." }

$miktexRoot = Join-Path $prefix "Library\MiKTeX"
$miktexBin = Join-Path $miktexRoot "miktex\bin\x64"
$pdflatex = Join-Path $miktexBin "pdflatex.exe"
if (-not (Test-Path -LiteralPath $pdflatex)) {
    $winget = Get-Command winget.exe -ErrorAction Stop
    Write-Host "==> Installing the MiKTeX engine inside the Conda environment" -ForegroundColor Cyan
    & $winget.Source install `
        --id MiKTeX.MiKTeX `
        --exact `
        --scope user `
        --location $miktexRoot `
        --silent `
        --accept-package-agreements `
        --accept-source-agreements `
        --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "MiKTeX installation failed." }
}

# conda-forge installs latexmk as a Perl script under bin/. Windows does not
# consider extensionless scripts executable, so expose a small CMD shim.
$wrapper = Join-Path $prefix "Scripts\latexmk.cmd"
$wrapperBody = @'
@echo off
"%~dp0..\Library\bin\perl.exe" "%~dp0..\bin\latexmk" %*
'@
Set-Content -LiteralPath $wrapper -Value $wrapperBody -Encoding ascii

$env:PATH = "$(Split-Path $wrapper);$miktexBin;$env:PATH"
Write-Host "==> Verifying latexmk and a real PDF build" -ForegroundColor Cyan
& $wrapper -v
if ($LASTEXITCODE -ne 0) { throw "latexmk is not executable." }
# MiKTeX may return a non-zero code for `--version` until its optional update
# check has been acknowledged; the real compilation below is authoritative.
& $pdflatex --version | Select-Object -First 2

$smokeDir = Join-Path ([System.IO.Path]::GetTempPath()) "researchos-latex-smoke-$PID"
New-Item -ItemType Directory -Path $smokeDir -Force | Out-Null
try {
    $source = @'
\documentclass{article}
\begin{document}
ResearchOS real-time PDF compilation is ready. $E=mc^2$.
\end{document}
'@
    Set-Content -LiteralPath (Join-Path $smokeDir "main.tex") -Value $source -Encoding ascii
    Push-Location $smokeDir
    try {
        & $wrapper -pdf -interaction=nonstopmode -halt-on-error -file-line-error -no-shell-escape main.tex
        if ($LASTEXITCODE -ne 0) { throw "LaTeX smoke compilation failed." }
    } finally {
        Pop-Location
    }
    $pdf = Join-Path $smokeDir "main.pdf"
    if (-not (Test-Path -LiteralPath $pdf)) { throw "LaTeX did not produce main.pdf." }
    $bytes = [System.IO.File]::ReadAllBytes($pdf)
    $header = [System.Text.Encoding]::ASCII.GetString($bytes, 0, [Math]::Min(8, $bytes.Length))
    if (-not $header.StartsWith("%PDF-")) { throw "The generated file is not a PDF." }
    Write-Host "LaTeX ready: $wrapper -> $pdflatex ($($bytes.Length) PDF bytes)" -ForegroundColor Green
} finally {
    Remove-Item -LiteralPath $smokeDir -Recurse -Force -ErrorAction SilentlyContinue
}
