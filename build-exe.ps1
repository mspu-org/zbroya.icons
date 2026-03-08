param(
    [string]$PythonExe = "C:\Program Files\Python313\python.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$env:TEMP = Join-Path $root "tmp"
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

& $PythonExe -m pip install -r requirements.txt pyinstaller

& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name IconPackStudio `
    --add-data "templates;templates" `
    --add-data "config.json;." `
    desktop_launcher.py

Write-Host "Build complete: $root\dist\IconPackStudio.exe"
