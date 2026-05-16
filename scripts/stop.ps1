$ErrorActionPreference = "Stop"

$container = "pm-app"

$existing = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $container }
if ($existing) {
    docker stop $container 2>$null | Out-Null
    docker rm $container 2>$null | Out-Null
    Write-Host "Stopped and removed $container."
} else {
    Write-Host "Container $container is not running."
}
