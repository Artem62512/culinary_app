$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Join-Path $projectRoot "backend"
$frontendRoot = Join-Path $projectRoot "frontend"
$pythonExe = Join-Path $backendRoot ".venv\Scripts\python.exe"
$npmExe = Join-Path $env:APPDATA "npm\npm.cmd"

function Test-PortListening {
    param([int]$Port)

    try {
        $connection = [System.Net.Sockets.TcpClient]::new()
        $connection.ReceiveTimeout = 200
        $connection.SendTimeout = 200
        $async = $connection.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(300, $false)) {
            $connection.Close()
            return $false
        }
        $connection.EndConnect($async)
        $connection.Close()
        return $true
    }
    catch {
        return $false
    }
}

if (-not (Test-Path $pythonExe)) {
    throw "Не найден backend\.venv\Scripts\python.exe"
}

if (-not (Test-Path (Join-Path $backendRoot ".env"))) {
    throw "Не найден backend\.env. Скопируйте backend\.env.example и задайте APP_USERNAME и APP_PASSWORD."
}

if (-not (Test-Path (Join-Path $frontendRoot "package.json"))) {
    throw "Не найдена папка frontend"
}

if (-not (Test-Path (Join-Path $frontendRoot "node_modules\vite\bin\vite.js"))) {
    throw "Не найдены зависимости frontend. Выполните npm ci в папке frontend."
}

if (-not (Test-PortListening -Port 8000)) {
    Start-Process -FilePath $pythonExe `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $backendRoot
}

if (-not (Test-PortListening -Port 5173)) {
    if (Test-Path $npmExe) {
        Start-Process -FilePath $npmExe `
            -ArgumentList "run", "dev", "--", "--host", "127.0.0.1" `
            -WorkingDirectory $frontendRoot
    }
    else {
        Start-Process -FilePath "npm.cmd" `
            -ArgumentList "run", "dev", "--", "--host", "127.0.0.1" `
            -WorkingDirectory $frontendRoot
    }
}

$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    if ((Test-PortListening -Port 8000) -and (Test-PortListening -Port 5173)) {
        break
    }
    Start-Sleep -Milliseconds 300
}

Start-Process "http://127.0.0.1:5173/"
