@echo off
if "%1"=="seed" (
    python backend\app\services\ingestion\seed_loader.py
    exit /b %ERRORLEVEL%
)
if "%1"=="test" (
    python -m pytest backend\tests -v
    exit /b %ERRORLEVEL%
)
if "%1"=="frontend-build" (
    cd frontend && npm run build
    exit /b %ERRORLEVEL%
)
if "%1"=="frontend-test" (
    node frontend\test-e2e.mjs
    node frontend\test-step12.mjs
    node frontend\test-step13.mjs
    node frontend\test-step14.mjs
    node frontend\test-step15.mjs
    node frontend\test-step16.mjs
    node frontend\test-step17.mjs
    exit /b %ERRORLEVEL%
)
echo Usage: make [seed^|test^|frontend-build^|frontend-test]
exit /b 1
