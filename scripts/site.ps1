# ResearchOS fast local site launcher for Windows.
# Infrastructure runs in Docker; API, worker, and web run directly from this G-drive checkout.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/site.ps1 <up|down|restart|status|verify|logs>
param(
    [ValidateSet("up", "down", "restart", "status", "verify", "logs", "help")]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeDir = Join-Path $repoRoot "artifacts\site-runtime"
$apiPortFile = Join-Path $runtimeDir "api.port"
$apiDir = Join-Path $repoRoot "apps\api"
$workerDir = Join-Path $repoRoot "apps\worker"
$webDir = Join-Path $repoRoot "apps\web"
$composeFile = Join-Path $repoRoot "infra\docker\docker-compose.yml"

$alembicExe = Join-Path $apiDir ".venv\Scripts\alembic.exe"
$pythonExe = Join-Path $apiDir ".venv\Scripts\python.exe"
$nextBin = Join-Path $webDir "node_modules\next\dist\bin\next"

$apiPort = 8000
if ($env:RESEARCHOS_API_PORT -match "^\d+$") {
    $apiPort = [int]$env:RESEARCHOS_API_PORT
} elseif (Test-Path -LiteralPath $apiPortFile) {
    $savedApiPort = (Get-Content -LiteralPath $apiPortFile -Raw).Trim()
    if ($savedApiPort -match "^\d+$") { $apiPort = [int]$savedApiPort }
}
$apiBaseUrl = "http://localhost:$apiPort"

$postgresHostPort = 15432
if ($env:POSTGRES_HOST_PORT -match "^\d+$") {
    $postgresHostPort = [int]$env:POSTGRES_HOST_PORT
}
$env:POSTGRES_HOST_PORT = "$postgresHostPort"
$env:REDIS_HOST_PORT = "56379"
$env:ENVIRONMENT = "local"
$env:POSTGRES_DSN = "postgresql+asyncpg://researchos:researchos@localhost:$postgresHostPort/researchos"
$env:REDIS_URL = "redis://localhost:56379/0"
$env:S3_ENDPOINT_URL = "http://localhost:9000"
$env:CORS_ORIGINS = "http://localhost:3000"
$env:NEXT_PUBLIC_API_BASE_URL = $apiBaseUrl
$env:DB_USE_NULLPOOL = "true"
$env:WORKSPACE_ROOT = Join-Path $repoRoot "data\workspaces"

function Write-Step([string]$message) {
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Resolve-Docker {
    $command = Get-Command docker.exe -ErrorAction SilentlyContinue
    $candidates = @(
        $(if ($command) { $command.Source } else { $null }),
        "G:\Docker\DockerDesktop\resources\bin\docker.exe",
        "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe"
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    if (-not $candidates) {
        throw "Docker CLI was not found. Expected G:\Docker\DockerDesktop\resources\bin\docker.exe."
    }
    return @($candidates)[0]
}

function Test-DockerEngine([string]$dockerExe) {
    # Windows PowerShell can promote native stderr to a terminating error when
    # ErrorActionPreference is Stop. Docker emits stderr while Desktop is down,
    # so temporarily silence native command errors and rely on the exit code.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & $dockerExe info *> $null
        return $LASTEXITCODE -eq 0
    } finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Ensure-DockerEngine([string]$dockerExe) {
    if (Test-DockerEngine $dockerExe) { return }

    $desktopCandidates = @(
        "G:\Docker\DockerDesktop\Docker Desktop.exe",
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    ) | Where-Object { Test-Path -LiteralPath $_ }
    if (-not $desktopCandidates) {
        throw "Docker Desktop is installed but its launcher was not found."
    }

    Write-Step "Starting Docker Desktop"
    Start-Process -FilePath @($desktopCandidates)[0] -WindowStyle Hidden | Out-Null
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Seconds 1
        if (Test-DockerEngine $dockerExe) { return }
    }
    throw "Docker Engine did not become ready within 60 seconds."
}

function Test-Http([string]$url, [int]$timeoutSeconds = 3) {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSeconds
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
    } catch {
        return $false
    }
}

function Wait-Http([string]$name, [string]$url, [int]$seconds = 45) {
    for ($attempt = 0; $attempt -lt $seconds; $attempt++) {
        if (Test-Http $url) {
            Write-Host "    $name ready: $url" -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 1
    }
    throw "$name did not become ready at $url. Check artifacts\site-runtime logs."
}

function Get-RecordedPid([string]$name) {
    $pidFile = Join-Path $runtimeDir "$name.pid"
    if (-not (Test-Path -LiteralPath $pidFile)) { return $null }
    $rawPid = (Get-Content -LiteralPath $pidFile -Raw).Trim()
    if ($rawPid -notmatch "^\d+$") { return $null }
    return [int]$rawPid
}

function Test-RecordedProcess([string]$name) {
    $recordedPid = Get-RecordedPid $name
    if (-not $recordedPid) { return $false }
    return $null -ne (Get-Process -Id $recordedPid -ErrorAction SilentlyContinue)
}

function Start-RecordedProcess(
    [string]$name,
    [string]$filePath,
    [string[]]$argumentList,
    [string]$workingDirectory
) {
    if (Test-RecordedProcess $name) {
        Write-Host "    $name already running (PID $(Get-RecordedPid $name))" -ForegroundColor DarkGray
        return
    }
    $stdout = Join-Path $runtimeDir "$name.out.log"
    $stderr = Join-Path $runtimeDir "$name.err.log"
    $process = Start-Process `
        -FilePath $filePath `
        -ArgumentList $argumentList `
        -WorkingDirectory $workingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
    Set-Content -LiteralPath (Join-Path $runtimeDir "$name.pid") -Value $process.Id -Encoding ascii
    Write-Host "    $name started (PID $($process.Id))" -ForegroundColor Green
}

function Stop-RecordedProcess([string]$name) {
    $pidFile = Join-Path $runtimeDir "$name.pid"
    $recordedPid = Get-RecordedPid $name
    if ($recordedPid) {
        $process = Get-Process -Id $recordedPid -ErrorAction SilentlyContinue
        if ($process) {
            # Next.js may create a child server process. Only traverse the exact
            # process tree rooted at the PID written by this launcher.
            $allProcesses = Get-CimInstance Win32_Process
            $descendants = New-Object System.Collections.Generic.List[int]
            $queue = New-Object System.Collections.Generic.Queue[int]
            $queue.Enqueue($recordedPid)
            while ($queue.Count -gt 0) {
                $parentPid = $queue.Dequeue()
                foreach ($child in $allProcesses | Where-Object { $_.ParentProcessId -eq $parentPid }) {
                    $descendants.Add([int]$child.ProcessId)
                    $queue.Enqueue([int]$child.ProcessId)
                }
            }
            $descendantArray = $descendants.ToArray()
            [array]::Reverse($descendantArray)
            foreach ($childPid in $descendantArray) {
                Stop-Process -Id $childPid -Force -ErrorAction SilentlyContinue
            }
            Stop-Process -Id $recordedPid -Force -ErrorAction SilentlyContinue
            Write-Host "    $name stopped (PID $recordedPid)" -ForegroundColor Yellow
        }
    }
    if (Test-Path -LiteralPath $pidFile) {
        Remove-Item -LiteralPath $pidFile -Force
    }
}

function Assert-LocalDependencies {
    $required = @($alembicExe, $pythonExe, $nextBin)
    foreach ($path in $required) {
        if (-not (Test-Path -LiteralPath $path)) {
            throw "Missing local dependency: $path. Install workspace dependencies before starting the site."
        }
    }
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    if (-not $node) { throw "node.exe was not found in PATH." }
    return $node.Source
}

function Resolve-ApiPort {
    if (Test-RecordedProcess "api") { return }

    $explicitPort = $env:RESEARCHOS_API_PORT -match "^\d+$"
    $candidatePorts = if ($explicitPort) {
        @($script:apiPort)
    } else {
        @($script:apiPort) + @(18000..18020)
    }
    foreach ($candidatePort in $candidatePorts | Select-Object -Unique) {
        $listener = Get-NetTCPConnection `
            -LocalPort $candidatePort `
            -State Listen `
            -ErrorAction SilentlyContinue
        if (-not $listener) {
            if ($candidatePort -ne $script:apiPort) {
                Write-Host "    API port $($script:apiPort) is occupied; using $candidatePort" -ForegroundColor Yellow
            }
            $script:apiPort = $candidatePort
            $script:apiBaseUrl = "http://localhost:$candidatePort"
            $env:NEXT_PUBLIC_API_BASE_URL = $script:apiBaseUrl
            Set-Content -LiteralPath $apiPortFile -Value $candidatePort -Encoding ascii
            return
        }
    }
    throw "No available API port was found. Tried: $($candidatePorts -join ', ')."
}

function Start-Site {
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
    New-Item -ItemType Directory -Path $env:WORKSPACE_ROOT -Force | Out-Null
    $nodeExe = Assert-LocalDependencies
    $dockerExe = Resolve-Docker
    Ensure-DockerEngine $dockerExe
    Resolve-ApiPort

    Write-Step "Starting cached infrastructure images (Postgres, Redis, MinIO)"
    & $dockerExe compose -f $composeFile up -d postgres redis minio
    if ($LASTEXITCODE -ne 0) { throw "Docker infrastructure failed to start." }

    Write-Step "Applying migrations and loading idempotent demo data"
    Push-Location $apiDir
    try {
        & $alembicExe upgrade head
        if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
        & $pythonExe -m researchos.seed.demo
        if ($LASTEXITCODE -ne 0) { throw "Demo seed failed." }
    } finally {
        Pop-Location
    }

    Write-Step "Starting API, background agent worker, and web UI"
    Start-RecordedProcess "api" $pythonExe @("-m", "uvicorn", "researchos.main:app", "--host", "127.0.0.1", "--port", "$apiPort") $apiDir
    Start-RecordedProcess "worker" $pythonExe @("-m", "celery", "-A", "researchos_worker.app", "worker", "--loglevel=info", "--pool=solo", "--queues=agents,ingestion,runtime,latex,experiments,skills,default") $workerDir
    Start-RecordedProcess "web" $nodeExe @($nextBin, "dev", "-p", "3000") $webDir

    Wait-Http "API" "$apiBaseUrl/healthz"
    Wait-Http "Web" "http://localhost:3000/login"
    Wait-Http "Dependencies" "$apiBaseUrl/readyz"

    Write-Host ""
    Write-Host "ResearchOS is ready." -ForegroundColor Green
    Write-Host "  Web:      http://localhost:3000/login"
    Write-Host "  API docs: $apiBaseUrl/docs"
    Write-Host "  Account:  demo@researchos.dev / demo-password-123"
    Write-Host "  Logs:     artifacts\site-runtime"
}

function Stop-Site {
    Write-Step "Stopping locally launched services"
    Stop-RecordedProcess "web"
    Stop-RecordedProcess "worker"
    Stop-RecordedProcess "api"

    $dockerExe = Resolve-Docker
    if (Test-DockerEngine $dockerExe) {
        Write-Step "Stopping ResearchOS infrastructure containers"
        & $dockerExe compose -f $composeFile stop postgres redis minio
    }
}

function Show-Status {
    $dockerExe = Resolve-Docker
    Write-Host "ResearchOS local site status" -ForegroundColor Cyan
    foreach ($name in @("api", "worker", "web")) {
        $running = Test-RecordedProcess $name
        $pidValue = Get-RecordedPid $name
        $label = if ($running) { "RUNNING (PID $pidValue)" } else { "STOPPED" }
        $color = if ($running) { "Green" } else { "Yellow" }
        Write-Host ("  {0,-8} {1}" -f $name, $label) -ForegroundColor $color
    }
    Write-Host ("  web      {0}" -f $(if (Test-Http "http://localhost:3000/login") { "HTTP OK" } else { "HTTP DOWN" }))
    Write-Host ("  api      {0} ({1})" -f $(if (Test-Http "$apiBaseUrl/healthz") { "HTTP OK" } else { "HTTP DOWN" }), $apiBaseUrl)
    if (Test-DockerEngine $dockerExe) {
        & $dockerExe compose -f $composeFile ps postgres redis minio
    } else {
        Write-Host "  docker   ENGINE DOWN" -ForegroundColor Yellow
    }
}

function Verify-Site {
    Write-Step "Checking web and dependency readiness"
    if (-not (Test-Http "http://localhost:3000/login")) { throw "Web login page is unavailable." }
    if (-not (Test-Http "$apiBaseUrl/readyz")) { throw "API dependencies are not ready." }
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "smoke_api.ps1") -BaseUrl $apiBaseUrl
    if ($LASTEXITCODE -ne 0) { throw "API smoke test failed." }
    Write-Host "Website verification passed." -ForegroundColor Green
}

function Show-Logs {
    if (-not (Test-Path -LiteralPath $runtimeDir)) {
        Write-Host "No runtime logs yet."
        return
    }
    Get-ChildItem -LiteralPath $runtimeDir -Filter "*.log" | ForEach-Object {
        Write-Host "--- $($_.Name) ---" -ForegroundColor Cyan
        Get-Content -LiteralPath $_.FullName -Tail 30
    }
}

switch ($Command) {
    "up" { Start-Site }
    "down" { Stop-Site }
    "restart" { Stop-Site; Start-Site }
    "status" { Show-Status }
    "verify" { Verify-Site }
    "logs" { Show-Logs }
    default {
        Write-Host "ResearchOS fast local site launcher" -ForegroundColor Cyan
        Write-Host "  pnpm site:up       Start infrastructure + API + worker + web"
        Write-Host "  pnpm site:status   Show process, HTTP, and container status"
        Write-Host "  pnpm site:verify   Run readiness and authenticated API checks"
        Write-Host "  pnpm site:logs     Show recent service logs"
        Write-Host "  pnpm site:restart  Restart the complete local site"
        Write-Host "  pnpm site:down     Stop only ResearchOS services"
    }
}
