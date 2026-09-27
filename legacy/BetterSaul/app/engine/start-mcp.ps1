param(
  [string]$DataDir = "$env:LOCALAPPDATA\BetterSaul",
  [int]$Port = 8000
)

$py = Join-Path $DataDir "runtime\python\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$env:PYTHONPATH = $PSScriptRoot
$env:PORT = "$Port"
$env:BETTERSAUL_MCP_PORT = "$Port"
$logDir = Join-Path $DataDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "mcp.log"
Write-Host "BetterSaul MCP http://127.0.0.1:$Port/mcp"
$launcher = Join-Path $PSScriptRoot "run_mcp.py"
& $py $launcher --http --host 127.0.0.1 --port $Port *>> $log
exit $LASTEXITCODE
