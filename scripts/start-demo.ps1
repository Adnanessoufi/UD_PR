# Start or reuse the local demo without installing dependencies or exposing it on the network.
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendDir = Join-Path $projectRoot 'backend'
$frontendDir = Join-Path $projectRoot 'frontend'
$pythonPath = Join-Path $backendDir '.venv\Scripts\python.exe'
$vitePath = Join-Path $frontendDir 'node_modules\.bin\vite.cmd'
$logDir = Join-Path $projectRoot 'docs\demo-logs'
if (!(Test-Path -LiteralPath $pythonPath) -or !(Test-Path -LiteralPath $vitePath)) {
    throw 'Dependencies are missing. Follow the installation steps in README.md first.'
}
if (!(Test-Path -LiteralPath (Join-Path $backendDir '.env'))) {
    throw 'backend/.env is missing. Configure it before starting the demo.'
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
function Test-DemoEndpoint([string]$url) {
    try { return (Invoke-WebRequest -Uri $url -TimeoutSec 2 -UseBasicParsing).StatusCode -eq 200 }
    catch { return $false }
}
$backendUrl = 'http://127.0.0.1:8001/api/system/capabilities'
$frontendUrl = 'http://127.0.0.1:5173/'
if (!(Test-DemoEndpoint $backendUrl)) {
    $backendProcess = Start-Process -FilePath $pythonPath -WorkingDirectory $backendDir -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'backend.out.log') -RedirectStandardError (Join-Path $logDir 'backend.err.log')
    Write-Host "Backend process: $($backendProcess.Id)"
}
if (!(Test-DemoEndpoint $frontendUrl)) {
    $frontendProcess = Start-Process -FilePath $env:ComSpec -WorkingDirectory $frontendDir -ArgumentList @('/d','/c','node_modules\.bin\vite.cmd --host 127.0.0.1 --port 5173 --strictPort') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'frontend.out.log') -RedirectStandardError (Join-Path $logDir 'frontend.err.log')
    Write-Host "Frontend process: $($frontendProcess.Id)"
}
$deadline = (Get-Date).AddSeconds(30)
do {
    $backendReady = Test-DemoEndpoint $backendUrl
    $frontendReady = Test-DemoEndpoint $frontendUrl
    if ($backendReady -and $frontendReady) { break }
    Start-Sleep -Milliseconds 500
} while ((Get-Date) -lt $deadline)
if (!$backendReady -or !$frontendReady) { throw "Demo did not start. Inspect logs in $logDir; another process may own port 8001 or 5173." }
Write-Host 'Demo ready: http://127.0.0.1:5173/'
Write-Host 'Existing campaigns are preserved. No generation or publication was requested.'
