# Production Deployment Checklist

## Pre-Deployment
- [ ] All tests passed: python run_all_tests.py
- [ ] System audit passed: python audit_system.py
- [ ] Shadow mode run completed: python deploy\shadow_runner.py
- [ ] Pilot segment validated: python deploy\pilot_runner.py
- [ ] Configuration file reviewed: deploy\production_config.json
- [ ] Log directory created: logs/

## Deployment Steps
1. Start service: deploy\start_production.bat
2. Verify health: deploy\health_check.bat
3. Monitor for 5 minutes: deploy\monitor.ps1
4. Send test decision:
powershell -Command "Invoke-RestMethod -Method Post -Uri http://localhost:8080/decide -Body '{"combined_risk_score":0.5,"segment":{"customer_tier":"established","geography":"domestic"}}' -ContentType 'application/json'"
5. Verify thresholds: GET http://localhost:8080/thresholds/established|domestic

## Rollback Triggers
- Fraud loss exceeds ceiling by 10%
- False decline rate increases > 20% versus baseline
- Latency exceeds 5ms for 3 consecutive checks
- Service returns 5xx errors > 1% of requests

## Rollback Procedure
1. Execute: deploy\rollback.bat
2. Verify rollback: GET http://localhost:8080/health
3. Confirm previous thresholds active: GET http://localhost:8080/thresholds/established|domestic
4. Investigate root cause before re-deploying

## Post-Deployment Monitoring (First 24 Hours)
- Fraud loss per segment: hourly
- False decline rate: hourly
- Decision latency: continuous
- Ceiling usage: hourly
- Approval/Challenge/Decline rates: hourly
- Threshold table version: verify current

## Post-Deployment Monitoring (Ongoing)
- Cost-model drift: weekly
- Churn model calibration: weekly
- Segment review: monthly
- Counterfactual slice analysis: monthly
- Threshold refresh cadence: daily-weekly