# Windows PowerShell startup script
# Usage: .\start.ps1

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Mobileum Horizon" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$Root = $PSScriptRoot

# ── Step 1: Check .env ────────────────────────────────────────
if (-not (Test-Path "$Root\.env")) {
    Write-Host "[setup] Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item "$Root\.env.example" "$Root\.env"
}

# ── Step 2: Backend virtual environment ────────────────────────
$VenvDir = "$Root\.venv"
if (-not (Test-Path "$VenvDir\Scripts\python.exe")) {
    Write-Host "[backend] Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv $VenvDir
}

Write-Host "[backend] Installing Python dependencies..." -ForegroundColor Yellow
& "$VenvDir\Scripts\pip.exe" install -r "$Root\backend\requirements.txt" --quiet

# ── Step 3: Seed the database ──────────────────────────────────
# Skipped seeding as per user instruction

# ── Step 4: Frontend dependencies ─────────────────────────────
$NodeModules = "$Root\frontend\node_modules"
if (-not (Test-Path $NodeModules)) {
    Write-Host "[frontend] Installing npm dependencies..." -ForegroundColor Yellow
    Push-Location "$Root\frontend"
    npm install --silent
    Pop-Location
}

# ── Step 4b: Copy logo to frontend public assets ───────────────
$LogoDst = "$Root\frontend\public\assets\logo.png"
if (-not (Test-Path $LogoDst)) {
    New-Item -ItemType Directory -Force -Path "$Root\frontend\public\assets" | Out-Null
    Copy-Item "$Root\assets\logo.png" $LogoDst -ErrorAction SilentlyContinue
    Write-Host "[setup] Logo copied to frontend public assets." -ForegroundColor Gray
}

# ── Step 5: Start both servers ─────────────────────────────────
Write-Host ""
Write-Host "Starting backend  → http://localhost:8000" -ForegroundColor Green
Write-Host "Starting frontend → http://localhost:5173" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop both servers." -ForegroundColor Gray
Write-Host ""

# Start backend in background
$BackendJob = Start-Job -ScriptBlock {
    param($Root, $Venv)
    Set-Location $Root
    & "$Venv\Scripts\uvicorn.exe" backend.main:app --reload --port 8000
} -ArgumentList $Root, $VenvDir

# Start frontend (blocking, so Ctrl+C stops everything)
try {
    Push-Location "$Root\frontend"
    npm run dev
} finally {
    Write-Host "`nStopping backend..." -ForegroundColor Yellow
    Stop-Job $BackendJob -ErrorAction SilentlyContinue
    Remove-Job $BackendJob -ErrorAction SilentlyContinue
    Pop-Location
    Write-Host "All servers stopped." -ForegroundColor Gray
}
