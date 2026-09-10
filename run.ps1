# run.ps1 - PowerShell launcher for IndexForge-DB
$host.UI.RawUI.WindowTitle = "IndexForge-DB Server"
Set-Location $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       IndexForge-DB (KD-Tree + R-Tree Search)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

$pyCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pyCmd = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pyCmd = "python"
} elseif (Test-Path "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe") {
    $pyCmd = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"
}

if (-not $pyCmd) {
    Write-Host "[ERROR] Python was not found." -ForegroundColor Red
    Read-Host "Press Enter to exit..."
    exit 1
}

Write-Host "Using Python: $pyCmd" -ForegroundColor Green
Write-Host "Starting server on http://localhost:8004 ..." -ForegroundColor Yellow

Start-Process "http://localhost:8004"

& $pyCmd app.py
