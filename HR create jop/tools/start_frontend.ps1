# Starts the frontend_last Vite dev server (default port 5174).
# Usage: tools\start_frontend.ps1 [port] [VITE_API_BASE_URL]
#   port            default 5174
#   base url        e.g. http://localhost:8000/api/v1 to run against the local
#                   backend instead of the VITE_API_BASE_URL default (soal.help)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$fe = Join-Path $repo "frontend\frontend_last"
$env:ComSpec = "$env:SystemRoot\System32\cmd.exe"
$logDir = Join-Path $env:TEMP "opencode"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$port = if ($args.Count -gt 0) { $args[0] } else { "5174" }
if ($args.Count -gt 1) { $env:VITE_API_BASE_URL = $args[1] }

$conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue }

Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev", "--", "--port", $port, "--host", "127.0.0.1" `
    -WorkingDirectory $fe -RedirectStandardOutput (Join-Path $logDir "frontend_last.log") -RedirectStandardError (Join-Path $logDir "frontend_last.err.log") `
    -WindowStyle Hidden

Start-Sleep -Seconds 8
$c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($c) { Write-Output "frontend up PID=$($c.OwningProcess) at http://127.0.0.1:$port (logs: $logDir\frontend_last.log)" }
else { Write-Error "frontend failed to start; see $logDir\frontend_last.err.log" }