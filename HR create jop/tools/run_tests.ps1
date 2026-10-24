# Runs the full deterministic backend suite (all tests except -m soal).
# Requires Postgres on :5432 (docker compose up -d postgres from repo root).
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$py = Join-Path $repo "backend\.venv\Scripts\python.exe"
Set-Location (Join-Path $repo "backend")
Remove-Item Env:\SOAL_API_KEY -ErrorAction SilentlyContinue
& $py -m pytest -m "not soal" -q