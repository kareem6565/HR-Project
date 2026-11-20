# Starts the complete HERA + HR Manager Docker Compose stack.
#   tools\start_hera.ps1              # Start all services, using existing images
#   tools\start_hera.ps1 -Build       # Rebuild application images, then start
#   tools\start_hera.ps1 -InfraOnly   # Start only PostgreSQL + HR Manager
param(
    [switch]$InfraOnly,
    [switch]$Build
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$compose = Join-Path $repo "docker-compose.yml"
$projectName = "hr-ai-assistant"

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

$services = @("postgres", "hr_php", "hr_web")
if (-not $InfraOnly) {
    $services += @("backend", "frontend")
}

$composeArgs = @("compose", "-p", $projectName, "-f", $compose, "up", "-d")
if ($Build) {
    $composeArgs += "--build"
}
$composeArgs += $services

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    throw "Failed to start the HERA Docker services."
}

function Wait-ForHttp {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Url
    )

    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                Write-Output "$Name ready: $Url"
                return
            }
        } catch {
            Start-Sleep -Seconds 2
        }
    }

    throw "$Name did not become ready at $Url. Check: docker compose -p $projectName -f `"$compose`" logs $($services -join ' ')"
}

Wait-ForHttp -Name "HR Manager" -Url "http://localhost/BIC2_Mvp/login.php"
if (-not $InfraOnly) {
    Wait-ForHttp -Name "HERA API" -Url "http://localhost:8000/api/v1/health"
    Wait-ForHttp -Name "HERA frontend" -Url "http://localhost:8080/"
}

Write-Output "Startup complete. Existing database volumes were left in place."
