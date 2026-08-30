@echo off
echo Quick Production Test
echo ====================
echo.

echo 1. Health Check:
powershell -Command "try { $r = Invoke-RestMethod -Method Get -Uri http://localhost:8080/health -TimeoutSec 3; Write-Host '  PASS: Service healthy' } catch { Write-Host '  FAIL: Service unreachable' }"

echo.
echo 2. Decision Test:
powershell -Command "try { $body = '{\"combined_risk_score\":0.70,\"segment\":{\"customer_tier\":\"new\",\"geography\":\"domestic\"}}'; $r = Invoke-RestMethod -Method Post -Uri http://localhost:8080/decide -Body $body -ContentType 'application/json' -TimeoutSec 3; Write-Host ('  PASS: Decision=' + $r.decision + ', Version=' + $r.threshold_table_version) } catch { Write-Host '  FAIL: Decision request failed' }"

echo.
echo 3. Threshold Lookup:
powershell -Command "try { $r = Invoke-RestMethod -Method Get -Uri 'http://localhost:8080/thresholds/established|domestic' -TimeoutSec 3; Write-Host ('  PASS: t_challenge=' + $r.t_challenge + ', t_decline=' + $r.t_decline) } catch { Write-Host '  FAIL: Threshold lookup failed' }"

echo.
echo 4. Outcome Recording:
powershell -Command "try { $body = '{\"transaction_id\":\"test_' + (Get-Date -Format 'HHmmss') + '\",\"label\":\"is_false_decline\",\"value\":true}'; $r = Invoke-RestMethod -Method Post -Uri http://localhost:8080/outcome -Body $body -ContentType 'application/json' -TimeoutSec 3; Write-Host '  PASS: Outcome recorded' } catch { Write-Host '  FAIL: Outcome recording failed' }"

echo.
echo Test complete.
pause