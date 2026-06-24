$ErrorActionPreference = "SilentlyContinue"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPort = 8011
$script:backendProc = $null

# Cleanup function — kills all our child processes
function Cleanup {
    Write-Host "`nShutting down..."
    if ($script:backendProc -and !$script:backendProc.HasExited) {
        $script:backendProc.Kill()
        Write-Host "  [OK] Backend stopped"
    }
    # Also kill anything left on our ports
    foreach ($port in @($backendPort, 3000)) {
        Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "All clean. Bye!"
}

# Capture Ctrl+C to ensure cleanup runs
[Console]::CancelKeyPress += {
    Write-Host "`nCtrl+C detected, cleaning up..."
    Cleanup
    [Environment]::Exit(0)
}

try {
    Write-Host "============================================"
    Write-Host "   AI Photo Agent Launcher"
    Write-Host "============================================"
    Write-Host ""

    # -- 1. Docker Desktop --
    Write-Host "[1/6] Checking Docker..."
    $dockerOk = $false
    try { docker info 2>&1 | Out-Null; $dockerOk = $true } catch {}
    if (-not $dockerOk) {
        Write-Host "  Starting Docker Desktop..."
        Start-Process "C:\Users\31307\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe"
        Write-Host "  Waiting for Docker (max 60s)..."
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 2
            try { docker info 2>&1 | Out-Null; $dockerOk = $true; break } catch {}
        }
    }
    if (-not $dockerOk) {
        Write-Host "  [FAIL] Docker not available, skipping containers"
    } else {
        Write-Host "  [OK] Docker is ready"

        # -- 2. Start database --
        Write-Host "[2/6] Starting PostgreSQL + Redis..."
        Set-Location $ROOT
        docker compose up -d 2>&1 | Out-Null
        Write-Host "  [OK] Containers started"

        # -- 3. Wait for database --
        Write-Host "[3/6] Waiting for database..."
        for ($i = 0; $i -lt 15; $i++) {
            Start-Sleep -Seconds 1
            $ready = docker exec aiphoto-postgres pg_isready -U aiphoto 2>&1
            if ($LASTEXITCODE -eq 0) { break }
        }
        Write-Host "  [OK] Database is ready"
    }

    # -- 4. Clear old processes on our ports --
    Write-Host "[4/6] Clearing old processes..."
    foreach ($port in @($backendPort, 3000)) {
        Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "  [OK] Ports cleared"

    # -- 5. Start backend --
    Write-Host "[5/6] Starting backend (port $backendPort)..."
    $script:backendProc = Start-Process -NoNewWindow -PassThru -FilePath "python" `
        -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","$backendPort" `
        -WorkingDirectory "$ROOT\backend"
    Write-Host "  [OK] Backend started (pid=$($script:backendProc.Id))"

    # Wait for backend to be ready
    Write-Host "  Waiting for backend..."
    $backendReady = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:$backendPort/health" -TimeoutSec 2 -ErrorAction Stop
            if ($r.StatusCode -eq 200) { $backendReady = $true; break }
        } catch {}
    }
    if ($backendReady) {
        Write-Host "  [OK] Backend is ready"
    } else {
        Write-Host "  [WARN] Backend may still be starting..."
    }

    # -- 6. Start frontend (foreground — Ctrl+C kills this and triggers cleanup) --
    Write-Host "[6/6] Starting frontend..."
    Write-Host "============================================"
    Write-Host "  Backend:  http://localhost:$backendPort"
    Write-Host "  Frontend: http://localhost:3000"
    Write-Host "  Press Ctrl+C to stop all services"
    Write-Host "============================================"
    Write-Host ""
    Set-Location "$ROOT\frontend"
    npm run dev

} finally {
    Cleanup
}
