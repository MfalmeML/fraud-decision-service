@echo off
echo Health Check
echo.

powershell -Command "try { $r = Invoke-RestMethod -Method Get -Uri http://localhost:8080/health -TimeoutSec 5; Write-Host 'Status:' $r.status; Write-Host 'Version:' $r.version } catch { Write-Host 'ERROR: Service unreachable' }"

pause