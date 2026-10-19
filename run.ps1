$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) { Write-Host "Run .\install.ps1 first." -ForegroundColor Yellow; exit 1 }
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Start-Process notepad.exe -ArgumentList (Join-Path $PSScriptRoot ".env"); Write-Host "Add your Gemini key, save, then run .\run.ps1 again."; exit 0 }
& ".\.venv\Scripts\python.exe" app.py
