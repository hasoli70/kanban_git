$ErrorActionPreference = "Stop"

if (-not (Test-Path "Dockerfile")) {
    Write-Error "Run this script from the project root (Dockerfile not found)."
}

$image = "pm-app"
$container = "pm-app"

if (-not (Test-Path ".env")) {
    Write-Error ".env not found in project root. Copy .env.example to .env first."
}

if (-not (Test-Path "data")) {
    New-Item -ItemType Directory -Path "data" | Out-Null
}

Write-Host "Building image $image..."
docker build -t $image .
if ($LASTEXITCODE -ne 0) { throw "docker build failed" }

$existing = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $container }
if ($existing) {
    Write-Host "Removing existing container $container..."
    docker rm -f $container | Out-Null
}

Write-Host "Starting container $container..."
$dataPath = (Resolve-Path "data").Path
docker run -d `
    --name $container `
    -p 8000:8000 `
    --env-file .env `
    -v "${dataPath}:/app/data" `
    $image | Out-Null
if ($LASTEXITCODE -ne 0) { throw "docker run failed" }

Write-Host -NoNewline "Waiting for healthcheck"
for ($i = 0; $i -lt 60; $i++) {
    $status = (docker inspect --format "{{.State.Health.Status}}" $container) 2>$null
    if ($status -eq "healthy") {
        Write-Host ""
        Write-Host "Container is healthy. App available at http://localhost:8000/"
        exit 0
    }
    if ($status -eq "unhealthy") {
        Write-Host ""
        docker logs $container --tail 50
        Write-Error "Container reported unhealthy"
    }
    Write-Host -NoNewline "."
    Start-Sleep -Seconds 2
}

Write-Host ""
docker logs $container --tail 50
Write-Error "Timeout waiting for healthy status"
