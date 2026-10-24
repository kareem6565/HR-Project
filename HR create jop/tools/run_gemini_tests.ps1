# Runs the live Soal provider tests (live calls to soal.help, needs a key).
# Injects the SOAL_API_KEY from backend/.env into the process env and clears
# any environment SOAL_API_KEY so backend/.env stays authoritative.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo "backend\.venv\Scripts\python.exe"
$envFile = Join-Path $repo "backend\.env"
$k = ((Get-Content $envFile | Where-Object { $_ -match '^\s*SOAL_API_KEY\s*=\s*(\S+)' }) -replace '^\s*SOAL_API_KEY\s*=\s*', '').Trim()
if (-not $k) { Write-Error "no SOAL_API_KEY found in backend/.env" }
Remove-Item Env:\SOAL_API_KEY -ErrorAction SilentlyContinue
$env:SOAL_API_KEY = $k
Set-Location (Join-Path $repo "backend")
& $py -m pytest -m soal -q