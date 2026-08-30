# Monitoring script for production
while ($true) {
    Clear-Host
    Write-Host "=== Fraud Decision Service Monitor ===" -ForegroundColor Cyan
    Write-Host "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Host ""
    
    try {
        $health = Invoke-RestMethod -Method Get -Uri "http://localhost:8080/health" -TimeoutSec 2
        Write-Host "Status: $($health.status)" -ForegroundColor Green
        Write-Host "Version: $($health.version)"
    } catch {
        Write-Host "Status: UNREACHABLE" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "Press Ctrl+C to exit"
    Start-Sleep -Seconds 5
}