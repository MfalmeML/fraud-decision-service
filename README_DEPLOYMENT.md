# Fraud Decision Service - Deployment

## Quick Start

1. Start service:
deploy\start_production.bat

2. Health check:
deploy\health_check.bat


3. Rollback:
deploy\rollback.bat

4. Monitor:
powershell -ExecutionPolicy Bypass -File deploy\monitor.ps1

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | /decide | Make decision |
| POST | /outcome | Record outcome |
| POST | /publish | Publish threshold table |
| GET | /health | Health check |
| GET | /thresholds/{segment} | Get thresholds |
| GET | /outcome?transaction_id=&label= | Get outcome |

## Configuration

Edit `deploy\production_config.json` for:
- Threshold table
- Fraud ceiling
- Logging level
- Fallback settings

## Rollback

Trigger rollback via `deploy\rollback.bat` or POST to /publish with rollback version.

## Logs

Located in `logs/decision.log`.
