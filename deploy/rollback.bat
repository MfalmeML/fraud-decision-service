@echo off
echo Rollback to Last Known Good Table
echo.

powershell -Command "$body = @{table=@{}; version='rollback-' + (Get-Date -Format 'yyyyMMddTHHmmssZ')} | ConvertTo-Json; try { $r = Invoke-RestMethod -Method Post -Uri http://localhost:8080/publish -Body $body -ContentType 'application/json' -TimeoutSec 5; Write-Host 'Rollback success:' $r.success } catch { Write-Host 'ERROR: Rollback failed' }"

pause