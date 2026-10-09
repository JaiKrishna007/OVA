param(
    [string]$Target = "seed"
)

if ($Target -eq "seed") {
    python backend/app/services/ingestion/seed_loader.py
    exit $LASTEXITCODE
}
elseif ($Target -eq "test") {
    python -m pytest backend/tests -v
    exit $LASTEXITCODE
}
elseif ($Target -eq "frontend-build") {
    Set-Location frontend
    npm run build
    Set-Location ..
    exit $LASTEXITCODE
}
elseif ($Target -eq "frontend-test") {
    node frontend/test-e2e.mjs
    node frontend/test-step12.mjs
    node frontend/test-step13.mjs
    node frontend/test-step14.mjs
    node frontend/test-step15.mjs
    node frontend/test-step16.mjs
    node frontend/test-step17.mjs
    node frontend/test-step18.mjs
    exit $LASTEXITCODE
}
elseif ($Target -eq "eval") {
    $env:PYTHONPATH="backend"
    python -m app.eval.run_eval --adversarial
    exit $LASTEXITCODE
}
elseif ($Target -eq "run") {
    $env:PYTHONPATH="backend"
    python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
    exit $LASTEXITCODE
}
else {
    Write-Host "Usage: .\make.ps1 [seed|test|eval|run|frontend-build|frontend-test]"
    exit 1
}
