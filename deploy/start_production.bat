@echo off
echo Starting Fraud Decision Service - Production
echo.

set PYTHONPATH=%CD%
set CONFIG_FILE=deploy\production_config.json
set LOG_DIR=logs

if not exist %LOG_DIR% mkdir %LOG_DIR%

echo Configuration: %CONFIG_FILE%
echo Logs: %LOG_DIR%
echo.

python src\server.py

pause