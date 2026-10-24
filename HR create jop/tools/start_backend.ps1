# Starts the FastAPI backend on :8000 with the environment this machine needs.
#   - removes any inherited GEMINI_API_KEY so backend/.env wins (env-var precedence)
#   - restarts any existing :8000 listener
#   - logs to %TEMP%\opencode\backend.log / backend.err.log
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repo "backend"
$py = Join-Path $backend ".venv\Scripts\python.exe"
$logDir = Join-Path $env:TEMP "opencode"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $py)) { Write-Error "venv python not found at $py" }

$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

Remove-Item Env:\GEMINI_API_KEY -ErrorAction SilentlyContinue

Start-Process -FilePath $py -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $backend -RedirectStandardOutput (Join-Path $logDir "backend.log") -RedirectStandardError (Join-Path $logDir "backend.err.log") `
    -WindowStyle Hidden

Start-Sleep -Seconds 8
$c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($c) { Write-Output "backend up PID=$($c.OwningProcess) (logs: $logDir\backend.log)" }
else { Write-Error "backend failed to start; see $logDir\backend.err.log" }