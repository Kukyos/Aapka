#!/usr/bin/env bash
# Aapka — one command to run everything. Bash counterpart of run.ps1.
#
#   ./run.sh            start the server and both screens
#   ./run.sh -Setup     install dependencies first (run this once)
#   ./run.sh -Test      run the unit tests and the eval harness, then exit
#
# No Docker, no Postgres, no services to configure. That is deliberate: a teammate
# should be able to clone this repo and see it working in one step.

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prefer the repo venv, fall back to whatever python3 is on PATH.
if [[ -x "$root/.venv/bin/python" ]]; then
    python="$root/.venv/bin/python"
else
    python="$(command -v python3 || true)"
fi

setup=false
test=false
for arg in "$@"; do
    case "$arg" in
        -Setup|--setup|-setup) setup=true ;;
        -Test|--test|-test) test=true ;;
        -h|--help)
            echo "Usage: $0 [-Setup] [-Test]"
            echo "  (no flags)  start the server and both screens"
            echo "  -Setup      install dependencies first (run this once)"
            echo "  -Test       run the unit tests and the eval harness, then exit"
            exit 0
            ;;
        *) echo "Unknown argument: $arg" >&2; exit 1 ;;
    esac
done

say() {
    local colour="${2:-}"
    case "$colour" in
        Green) printf '  \033[0;32m%s\033[0m\n' "$1" ;;
        Yellow) printf '  \033[0;33m%s\033[0m\n' "$1" ;;
        Red) printf '  \033[0;31m%s\033[0m\n' "$1" ;;
        DarkGray) printf '  \033[0;90m%s\033[0m\n' "$1" ;;
        *) printf '  \033[0;36m%s\033[0m\n' "$1" ;;
    esac
}

echo ""
echo "  Aapka - pre-consultation intake terminal"
echo -e "  \033[0;90mSIH 2026 - PS 26047 - Ministry of Ayush\033[0m"
echo ""

# --------------------------------------------------------------------- checks
if [[ -z "$python" ]]; then
    say "Python is not on PATH. Install Python 3.11 or newer." "Red"; exit 1
fi
if ! command -v node >/dev/null 2>&1; then
    say "Node is not on PATH. Install Node 20 or newer." "Red"; exit 1
fi

# --------------------------------------------------------------------- setup
if $setup; then
    say "Installing Python packages..."
    "$python" -m pip install -q -r "$root/server/requirements.txt"
    say "Installing patient screen packages..."
    (cd "$root/patient" && npm install --silent)
    say "Installing doctor screen packages..."
    (cd "$root/doctor" && npm install --silent)
    say "Setup complete." "Green"
    echo ""
fi

if [[ ! -d "$root/patient/node_modules" ]]; then
    say "Dependencies are not installed. Run: ./run.sh -Setup" "Yellow"
    exit 1
fi

# --------------------------------------------------------------------- tests
if $test; then
    cd "$root/server"
    say "Unit tests"
    "$python" -m pytest tests -q
    echo ""
    say "Eval harness (offline: no network, no model)"
    "$python" -m eval.run_eval
    echo ""
    say "Budget sweep"
    "$python" -m eval.budget_sweep
    echo ""
    say "Patient screen checks"
    (cd "$root/patient" && node check.mjs)
    exit 0
fi

# --------------------------------------------------------------------- run
if [[ ! -f "$root/.env" ]]; then
    say "No .env file. Running fully offline - the deterministic paths work without one." "DarkYellow"
    say "Copy .env.example to .env and add GROQ_API_KEY to enable the model rungs." "DarkYellow"
    echo ""
fi

pids=()
cleanup() {
    say "Stopping..." "DarkGray"
    for pid in "${pids[@]:-}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
}
trap cleanup EXIT INT TERM

say "Starting the server on http://localhost:8000"
(
    cd "$root/server"
    exec "$python" -m uvicorn aapka.api:app --port 8000
) &
pids+=("$!")

sleep 3

say "Starting the patient kiosk on http://localhost:5173"
(
    cd "$root/patient"
    exec npm run dev
) &
pids+=("$!")

say "Starting the doctor screen on http://localhost:5174"
(
    cd "$root/doctor"
    exec npm run dev
) &
pids+=("$!")

sleep 4
echo ""
say "Patient kiosk   http://localhost:5173" "Green"

# The phone-handoff QR on the attract screen points here. Printed so a demo can check
# the address is reachable before a judge scans it.
handoff=""
handoff="$(curl -s --max-time 2 "http://localhost:8000/api/handoff" 2>/dev/null \
    | sed -n 's/.*"url":"\([^"]*\)".*/\1/p' || true)"
if [[ -n "$handoff" ]]; then
    say "Patient phone   $handoff   (the QR on the attract screen)" "Green"
else
    say "Patient phone   no LAN address found - the kiosk will show no QR" "DarkYellow"
fi

say "Doctor screen   http://localhost:5174   (token: demo-doctor-token)" "Green"
say "Server health   http://localhost:8000/api/health" "Green"
echo ""
say "Use Chrome - the kiosk uses its built-in speech recognition and synthesis." "DarkGray"
say "Press Ctrl+C to stop everything." "DarkGray"
echo ""

if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://localhost:5173" >/dev/null 2>&1 || true
fi

wait