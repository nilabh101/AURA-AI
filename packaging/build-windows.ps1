$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment not found at .venv. Create it with Python 3.11 and install requirements first." }
if (-not (Test-Path (Join-Path $ProjectRoot "app.py"))) { throw "app.py was not found in the project root." }
Write-Host "Checking Python syntax..." -ForegroundColor Cyan
& $Python -m py_compile (Join-Path $ProjectRoot "app.py")
if ($LASTEXITCODE -ne 0) { throw "Syntax check failed." }
Write-Host "Building AURA-AI with PyInstaller..." -ForegroundColor Cyan
& $Python -m PyInstaller --noconfirm --clean --windowed --onedir --name "AURA-AI" --collect-all elevenlabs --collect-all google.genai --collect-all PySide6 --hidden-import sounddevice --hidden-import soundfile --hidden-import pyttsx3.drivers.sapi5 (Join-Path $ProjectRoot "app.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed. Scroll up for the error." }
$OutputDir = Join-Path $ProjectRoot "dist\AURA-AI"
if (Test-Path (Join-Path $ProjectRoot ".env.example")) { Copy-Item (Join-Path $ProjectRoot ".env.example") (Join-Path $OutputDir ".env.example") -Force }
if (Test-Path (Join-Path $ProjectRoot "README.md")) { Copy-Item (Join-Path $ProjectRoot "README.md") (Join-Path $OutputDir "README.txt") -Force }
Write-Host "Build completed: $OutputDir" -ForegroundColor Green
Write-Host "Test on a clean Windows machine before publishing. Do not copy your personal .env or API keys into the release." -ForegroundColor Yellow
