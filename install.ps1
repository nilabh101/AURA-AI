$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv")) { py -3.11 -m venv .venv }
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
Start-Process notepad.exe -ArgumentList (Join-Path $PSScriptRoot ".env")
Write-Host "Paste your Gemini API key into .env, save, then run .\run.ps1" -ForegroundColor Green
