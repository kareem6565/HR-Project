# One-command local setup for a fresh clone of the HERA platform.
#
#   tools\setup_local.ps1
#
# It creates the local .env files with generated secrets, installs the
# backend and frontend dependencies, applies the database migrations, seeds
# the sign-in data, and starts the whole stack (PostgreSQL, Nginx + PHP-FPM,
# FastAPI backend, and the Vite frontend).
#
# Requirements: Docker Desktop, Python 3.11+, Node.js/npm.
param([switch]$SkipStart)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repo "backend"
$frontend = Join-Path $repo "frontend\frontend_last"
$hrManager = Join-Path (Split-Path -Parent $repo) "HR manager"

function New-Secret([int]$length = 48) {
    $bytes = New-Object byte[] $length
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_').TrimEnd('=')
}

$sharedSecret = New-Secret
$jwtSecret = New-Secret

# ── Backend environment ────────────────────────────────────────────────────────
$backendEnv = Join-Path $backend ".env"
if (-not (Test-Path $backendEnv)) {
    Copy-Item (Join-Path $backend ".env.example") $backendEnv
    $content = Get-Content $backendEnv -Raw
    $content = $content -replace 'JWT_SECRET_KEY=.*', "JWT_SECRET_KEY=$jwtSecret"
    $content = $content -replace 'HR_SSO_SHARED_SECRET=.*', "HR_SSO_SHARED_SECRET=$sharedSecret"
    $content = $content -replace 'HR_SSO_ORGANIZATION_ID=.*', "HR_SSO_ORGANIZATION_ID=83d952e6-a8bb-45c2-b7e2-4ce18f013e66"
    Set-Content -Path $backendEnv -Value $content -Encoding UTF8
    Write-Output "created backend/.env with generated secrets"
} else {
    Write-Output "backend/.env already exists (left untouched)"
    $existing = Get-Content $backendEnv | Where-Object { $_ -match '^HR_SSO_SHARED_SECRET=(.+)$' }
    if ($existing) {
        $sharedSecret = ($existing -split '=', 2)[1].Trim()
    }
}

# ── HR Manager environment (must share the SSO secret) ─────────────────────────
$hrEnv = Join-Path $hrManager ".env"
if (-not (Test-Path $hrEnv)) {
    @(
        "# Use the same high-entropy value as HR_SSO_SHARED_SECRET in HR create jop/backend/.env.",
        "HERA_SSO_SHARED_SECRET=$sharedSecret",
        "HERA_SSO_ISSUER=hr-manager",
        "# HERA recruitment frontend URL (Vite local default shown here).",
        "HERA_FRONTEND_URL=http://localhost:5174",
        "# Set true when HTTPS terminates at a trusted reverse proxy; direct HTTPS is detected automatically.",
        "HERA_SECURE_COOKIES=false"
    ) | Set-Content -Path $hrEnv -Encoding UTF8
    Write-Output "created HR manager/.env with the matching SSO secret"
} else {
    Write-Output "HR manager/.env already exists (left untouched)"
}

# ── Frontend environment ───────────────────────────────────────────────────────
$frontendEnv = Join-Path $frontend ".env"
if (-not (Test-Path $frontendEnv)) {
    Copy-Item (Join-Path $frontend ".env.example") $frontendEnv
    Add-Content -Path $frontendEnv -Encoding UTF8 -Value @(
        "VITE_HR_MANAGER_URL=http://localhost/BIC2_Mvp/workspace.php",
        "VITE_HR_MANAGER_LOGOUT_URL=http://localhost/BIC2_Mvp/logout.php"
    )
    Write-Output "created frontend/frontend_last/.env"
} else {
    Write-Output "frontend/.env already exists (left untouched)"
}

# ── Backend dependencies, migrations, and seed data ────────────────────────────
$python = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Output "creating backend virtual environment"
    python -m venv (Join-Path $backend ".venv")
    & $python -m pip install --upgrade pip | Out-Null
    & $python -m pip install -e "${backend}[dev]" | Out-Null
}

Push-Location $backend
& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "alembic upgrade head failed" }
& $python "..\tools\bootstrap_hera_org.py"
& $python "..\tools\seed_hr_manager.py"
Pop-Location

# ── Frontend dependencies ──────────────────────────────────────────────────────
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Output "installing frontend dependencies"
    Push-Location $frontend
    npm install
    Pop-Location
}

Write-Output ""
Write-Output "setup complete. HR sign-in: employee code HR001 (password: hr123)"
Write-Output "change the seeded password before real use."

if (-not $SkipStart) {
    & (Join-Path $PSScriptRoot "start_hera.ps1")
}
