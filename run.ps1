# Aapka — one command to run everything.
#
#   .\run.ps1            start the server and both screens
#   .\run.ps1 -Setup     install dependencies first (run this once)
#   .\run.ps1 -Test      run the unit tests and the eval harness, then exit
#
# No Docker, no Postgres, no services to configure. That is deliberate: a teammate
# should be able to clone this repo and see it working in one step.

[CmdletBinding()]
param(
    [switch]$Setup,
    [switch]$Test
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Say($message, $colour = "Cyan") { Write-Host "  $message" -ForegroundColor $colour }

Write-Host ""
Write-Host "  Aapka - pre-consultation intake terminal" -ForegroundColor White
Write-Host "  SIH 2026 - PS 26047 - Ministry of Ayush" -ForegroundColor DarkGray
Write-Host ""

# --------------------------------------------------------------------- checks
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { Say "Python is not on PATH. Install Python 3.11 or newer." "Red"; exit 1 }
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { Say "Node is not on PATH. Install Node 20 or newer." "Red"; exit 1 }

# --------------------------------------------------------------------- setup
if ($Setup) {
    Say "Installing Python packages..."
    python -m pip install -q -r "$root\server\requirements.txt"
    Say "Installing patient screen packages..."
    Push-Location "$root\patient"; npm install --silent; Pop-Location
    Say "Installing doctor screen packages..."
    Push-Location "$root\doctor"; npm install --silent; Pop-Location
    Say "Setup complete." "Green"
    Write-Host ""
}

if (-not (Test-Path "$root\patient\node_modules")) {
    Say "Dependencies are not installed. Run: .\run.ps1 -Setup" "Yellow"
    exit 1
}

# --------------------------------------------------------------------- tests
if ($Test) {
    Push-Location "$root\server"
    Say "Unit tests"
    python -m pytest tests -q
    $testsFailed = $LASTEXITCODE
    Write-Host ""
    Say "Eval harness (offline: no network, no model)"
    python -m eval.run_eval
    $evalFailed = $LASTEXITCODE
    Write-Host ""
    Say "Budget sweep"
    python -m eval.budget_sweep
    Pop-Location
    Write-Host ""
    Say "Patient screen checks"
    Push-Location "$root\patient"; node check.mjs; $clientFailed = $LASTEXITCODE; Pop-Location
    if ($testsFailed -ne 0 -or $evalFailed -ne 0 -or $clientFailed -ne 0) { exit 1 }
    exit 0
}

# --------------------------------------------------------------------- run
if (-not (Test-Path "$root\.env")) {
    Say "No .env file. Running fully offline - the deterministic paths work without one." "DarkYellow"
    Say "Copy .env.example to .env and add GROQ_API_KEY to enable the model rungs." "DarkYellow"
    Write-Host ""
}

$jobs = @()
Say "Starting the server on http://localhost:8000"
$jobs += Start-Process -PassThru -WindowStyle Minimized -WorkingDirectory "$root\server" `
    -FilePath "python" -ArgumentList "-m", "uvicorn", "aapka.api:app", "--port", "8000"

Start-Sleep -Seconds 3

Say "Starting the patient kiosk on http://localhost:5173"
$jobs += Start-Process -PassThru -WindowStyle Minimized -WorkingDirectory "$root\patient" `
    -FilePath "cmd" -ArgumentList "/c", "npm", "run", "dev"

Say "Starting the doctor screen on http://localhost:5174"
$jobs += Start-Process -PassThru -WindowStyle Minimized -WorkingDirectory "$root\doctor" `
    -FilePath "cmd" -ArgumentList "/c", "npm", "run", "dev"

Start-Sleep -Seconds 4
Write-Host ""
Say "Patient kiosk   http://localhost:5173" "Green"

# The phone-handoff QR on the attract screen points here. Printed so a demo can check
# the address is reachable before a judge scans it.
$handoff = $null
try { $handoff = (Invoke-RestMethod "http://localhost:8000/api/handoff" -ErrorAction Stop).url } catch { }
if ($handoff) { Say "Patient phone   $handoff   (the QR on the attract screen)" "Green" }
else { Say "Patient phone   no LAN address found - the kiosk will show no QR" "DarkYellow" }

Say "Doctor screen   http://localhost:5174   (token: demo-doctor-token)" "Green"
Say "Server health   http://localhost:8000/api/health" "Green"
Write-Host ""
Say "Use Chrome - the kiosk uses its built-in speech recognition and synthesis." "DarkGray"
Say "Press Ctrl+C to stop everything." "DarkGray"
Write-Host ""

Start-Process "http://localhost:5173"

try {
    while ($true) { Start-Sleep -Seconds 2 }
}
finally {
    Say "Stopping..." "DarkGray"
    foreach ($job in $jobs) {
        if ($job -and -not $job.HasExited) {
            Stop-Process -Id $job.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
