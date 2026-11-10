# Starts HERA without XAMPP, Apache, or MySQL.
#   tools\start_hera.ps1              # PostgreSQL + Nginx/PHP + backend + frontend
#   tools\start_hera.ps1 -InfraOnly   # PostgreSQL + Nginx/PHP (HR Manager only)
param([switch]$InfraOnly)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$compose = Join-Path $repo "docker-compose.yml"

$dockerReady = $false
try {
    docker version --format '{{.Server.Version}}' | Out-Null
    $dockerReady = $LASTEXITCODE -eq 0
} catch {
    $dockerReady = $false
}

if (-not $dockerReady) {
    $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerDesktop)) {
        throw "Docker Desktop is required but was not found at $dockerDesktop"
    }
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden

    for ($attempt = 0; $attempt -lt 36; $attempt++) {
        Start-Sleep -Seconds 5
        docker version --format '{{.Server.Version}}' 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $dockerReady = $true
            break
        }
    }
}
if (-not $dockerReady) {
    throw "Docker did not become ready. Open Docker Desktop and retry."
}

& docker compose -f $compose up -d postgres hr_php hr_web
if ($LASTEXITCODE -ne 0) {
    throw "Failed to start the HERA Docker services."
}

$hrReady = $false
for ($attempt = 0; $attempt -lt 12; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost/BIC2_Mvp/login.php" `
            -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            $hrReady = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 3
    }
}
if (-not $hrReady) {
    throw "HR Manager did not become ready. Check: docker compose logs hr_php hr_web"
}
Write-Output "HR Manager: http://localhost/BIC2_Mvp/login.php"

if (-not $InfraOnly) {
    & (Join-Path $PSScriptRoot "start_backend.ps1")
    & (Join-Path $PSScriptRoot "start_frontend.ps1") 5174 http://localhost:8000/api/v1
    Write-Output "Recruitment frontend: http://127.0.0.1:5174"
}
