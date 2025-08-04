Param(
  [switch]$VerboseLogs
)

# Stop script for GraphRAG stack
# - Gracefully stops React dev server, FastAPI (uvicorn) API, Python workers
# - Brings down container stack via podman-compose.dev.yml if present
# - Kills straggler Node/Python processes bound to our project dir
# - Cleans sockets/ports if necessary

$ErrorActionPreference = 'SilentlyContinue'

function Info([string]$msg) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Write-Host ("[{0}] [INFO] {1}" -f $ts, $msg)
}

function Warn([string]$msg) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Write-Host ("[{0}] [WARN] {1}" -f $ts, $msg) -ForegroundColor Yellow
}

function Err([string]$msg) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Write-Host ("[{0}] [ERROR] {1}" -f $ts, $msg) -ForegroundColor Red
}

# Helper: stop processes by name that are running under the workspace
function Stop-ProcsInWorkspace {
  param([string]$processName)
  try {
    $workspace = (Get-Location).Path
    $procs = Get-Process -Name $processName -ErrorAction SilentlyContinue
    if ($procs) {
      $stopped = 0
      foreach ($p in $procs) {
        # Attempt to scope by command line when available
        $cmdline = ""
        try {
          $wmi = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $p.Id)
          $cmdline = $wmi.CommandLine
        } catch { }

        if ($cmdline -and $cmdline -like ("*{0}*" -f $workspace)) {
          Info ("Stopping process: {0} (PID {1})" -f $processName, $p.Id)
          Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
          $stopped++
        } elseif (-not $cmdline) {
          try {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
            $stopped++
          } catch { }
        }
      }
      if ($stopped -gt 0) { Info ("Stopped {0} {1} process(es)" -f $stopped, $processName) }
    }
  } catch {
    Warn ("Failed to enumerate/stop {0}: {1}" -f $processName, ($_.Exception.Message))
  }
}

# 1) Stop dev servers and API first
Info "Stopping Node (React dev server) processes in workspace..."
Stop-ProcsInWorkspace -processName "node"

Info "Stopping Python (uvicorn, workers) processes in workspace..."
Stop-ProcsInWorkspace -processName "python"

# 2) Bring down container stack (podman-compose or docker-compose)
$composeFiles = @(
  "podman-compose.dev.yml",
  "docker-compose.dev.yml",
  "docker-compose.yml"
)

function Bring-DownCompose {
  param([string]$file)
  $path = Join-Path (Get-Location) $file
  if (Test-Path $path) {
    try {
      if ($file -like "podman-*") {
        Info ("Bringing down compose stack: {0}" -f $file)
        podman-compose -f $file down | Out-Null
      } else {
        Info ("Bringing down docker compose stack: {0}" -f $file)
        docker compose -f $file down | Out-Null
      }
    } catch {
      Warn ("Compose down failed for {0}: {1}" -f $file, ($_.Exception.Message))
    }
  }
}

foreach ($f in $composeFiles) {
  Bring-DownCompose -file $f
}

# 3) Double-check common ports and kill listeners if still hanging (optional)
function Free-Port {
  param([int]$port)
  try {
    $net = netstat -ano | Select-String "LISTENING" | Select-String (":{0} " -f $port)
    if ($net) {
      $pid = ($net -split "\s+")[-1]
      if ($pid -match "^\d+$") {
        Info ("Port {0} is in use by PID {1}; attempting to stop" -f $port, $pid)
        Stop-Process -Id ([int]$pid) -Force -ErrorAction SilentlyContinue
      }
    }
  } catch { }
}

# Only free the dev/UI/API ports; infra ports belong to containers and should be handled by compose down
Free-Port -port 3000
Free-Port -port 8080

# 4) Optional: verbose diagnostics
if ($VerboseLogs) {
  Info "Verbose mode enabled - printing remaining Node/Python processes"
  Get-Process node, python -ErrorAction SilentlyContinue | Format-Table -AutoSize
}

Info "Stop sequence completed."