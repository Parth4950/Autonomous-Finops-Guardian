param(
    [string]$BackendUrl = "http://localhost:8000/health",
    [string]$FrontendUrl = "http://localhost:8080/"
)

$ErrorActionPreference = "Stop"
$health = Invoke-RestMethod -Uri $BackendUrl -Method Get
if ($health.status -ne "healthy") {
    throw "Backend returned unexpected status: $($health.status)"
}
Invoke-WebRequest -Uri $FrontendUrl -Method Get -UseBasicParsing | Out-Null
Write-Output "Backend and frontend health checks passed."
