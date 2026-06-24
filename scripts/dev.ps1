# ResearchOS dev helper (PowerShell)
# Usage: .\scripts\dev.ps1 <command>
# Commands: full | up | down | migrate | seed | test | smoke | check | help
param($cmd = "help")

$ErrorActionPreference = "Stop"
$compose = "docker compose -f infra/docker/docker-compose.yml"
$testCompose = "$compose -f infra/docker/docker-compose.test.yml"

function ensure_pnpm {
    if (!(Get-Command pnpm -ErrorAction SilentlyContinue)) {
        Write-Host "pnpm not found. Try:" -Fore Yellow
        Write-Host "  corepack enable"
        Write-Host "  corepack prepare pnpm@9.15.0 --activate"
        exit 1
    }
}

switch ($cmd) {
    "full" {
        Write-Host "=== ResearchOS: full reset ===" -Fore Cyan
        docker compose -f infra/docker/docker-compose.yml down 2>$null
        docker compose -f infra/docker/docker-compose.yml up -d --build
        Start-Sleep -Seconds 8
        docker compose -f infra/docker/docker-compose.yml exec -T api alembic upgrade head
        docker compose -f infra/docker/docker-compose.yml exec -T api python -m researchos.seed.demo
        Write-Host "Done. Web: http://localhost:3000 | API: http://localhost:8000/docs" -Fore Green
    }
    "up" {
        docker compose -f infra/docker/docker-compose.yml up -d --build
        Write-Host "Stack starting. Wait ~10s then run: migrate, seed" -Fore Green
    }
    "down" {
        docker compose -f infra/docker/docker-compose.yml down
    }
    "migrate" {
        docker compose -f infra/docker/docker-compose.yml exec -T api alembic upgrade head
    }
    "seed" {
        docker compose -f infra/docker/docker-compose.yml exec -T api python -m researchos.seed.demo
    }
    "test" {
        docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.test.yml run --rm test
    }
    "smoke" {
        powershell -ExecutionPolicy Bypass -File "$PSScriptRoot/smoke_api.ps1"
    }
    "check" {
        ensure_pnpm
        Write-Host "=== Backend (in-network pytest) ===" -Fore Cyan
        docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.test.yml run --rm test
        Write-Host "=== Frontend typecheck + build ===" -Fore Cyan
        pnpm -r typecheck
        pnpm --filter web build
        Write-Host "All checks passed." -Fore Green
    }
    default {
        Write-Host "ResearchOS dev helper" -Fore Cyan
        Write-Host "  .\scripts\dev.ps1 full    - down -> up -> migrate -> seed"
        Write-Host "  .\scripts\dev.ps1 up      - start all services"
        Write-Host "  .\scripts\dev.ps1 down    - stop all services"
        Write-Host "  .\scripts\dev.ps1 migrate - apply database migrations"
        Write-Host "  .\scripts\dev.ps1 seed    - seed demo data (idempotent)"
        Write-Host "  .\scripts\dev.ps1 test    - run backend tests"
        Write-Host "  .\scripts\dev.ps1 smoke   - run API smoke test"
        Write-Host "  .\scripts\dev.ps1 check   - full quality gate"
    }
}
