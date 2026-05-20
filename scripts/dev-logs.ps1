param(
  [string]$ApiUrl = "",
  [int]$PollSeconds = 2,
  [int]$Tail = 120,
  [switch]$NoBackendFile,
  [switch]$NoDebugApi,
  [switch]$NoDocker,
  [switch]$NoAdb,
  [switch]$NoCodexLogs,
  [switch]$RawAndroid,
  [switch]$StartCli,
  [switch]$Once
)

$ErrorActionPreference = "Continue"
$Root = (Resolve-Path "$PSScriptRoot\..").Path
$LogDir = Join-Path $Root ".codex-logs"
$BackendLog = Join-Path $Root "apps\backend\logs\devlink.log"
$CombinedLog = Join-Path $LogDir ("devlink-live-" + (Get-Date -Format "yyyyMMdd-HHmmss") + "-$PID.log")

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Normalize-BaseUrl([string]$Value) {
  $base = $Value.Trim().TrimEnd("/")
  if ($base.EndsWith("/api")) {
    return $base.Substring(0, $base.Length - 4)
  }
  return $base
}

function Get-LocalLanIp() {
  try {
    $wifi = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
      Where-Object { $_.InterfaceAlias -eq "Wi-Fi" -and $_.IPAddress -notlike "169.254.*" } |
      Select-Object -First 1
    if ($wifi -and $wifi.IPAddress) { return [string]$wifi.IPAddress }
  } catch { }

  try {
    $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
      Sort-Object RouteMetric,InterfaceMetric |
      Select-Object -First 1
    if ($route -and $route.InterfaceIndex) {
      $ip = Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "169.254.*" } |
        Select-Object -First 1
      if ($ip -and $ip.IPAddress) { return [string]$ip.IPAddress }
    }
  } catch { }

  return "127.0.0.1"
}

function Has-Command([string]$Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Write-LogLine([string]$Line) {
  $stamp = Get-Date -Format "HH:mm:ss.fff"
  $full = "$stamp $Line"
  try {
    Add-Content -Path $CombinedLog -Value $full -Encoding UTF8
  } catch {
    Write-Host "[dev-logs] could not write combined log: $($_.Exception.Message)" -ForegroundColor Yellow
  }

  $color = "Gray"
  if ($Line -match "^\[api-error\]" -or $Line -match "HTTP 5\d\d" -or $Line -match "Traceback|Exception|ERROR") { $color = "Red" }
  elseif ($Line -match "^\[api-request\].*( 4\d\d| 5\d\d|-> 4\d\d|-> 5\d\d)") { $color = "Yellow" }
  elseif ($Line -match "^\[adb\]") { $color = "Cyan" }
  elseif ($Line -match "^\[docker\]") { $color = "DarkCyan" }
  elseif ($Line -match "^\[backend-file\]") { $color = "Green" }
  elseif ($Line -match "^\[cli\]") { $color = "Magenta" }
  elseif ($Line -match "^\[codex:") { $color = "DarkYellow" }
  Write-Host $full -ForegroundColor $color
}

function Start-LogJob([string]$Name, [scriptblock]$Script, [object[]]$ArgsList) {
  $job = Start-Job -Name $Name -ScriptBlock $Script -ArgumentList $ArgsList
  Write-LogLine "[dev-logs] started job: $Name"
  return $job
}

$ResolvedApiUrl = $ApiUrl
if (-not $ResolvedApiUrl.Trim()) {
  $ip = Get-LocalLanIp
  $ResolvedApiUrl = "http://$ip`:8000"
}
$BaseUrl = Normalize-BaseUrl $ResolvedApiUrl
$jobs = @()

Write-LogLine "[dev-logs] root: $Root"
Write-LogLine "[dev-logs] combined log file: $CombinedLog"
Write-LogLine "[dev-logs] backend debug url: $BaseUrl/devlink-debug/"

if (-not $NoBackendFile) {
  $jobs += Start-LogJob "backend-file" {
    param($Path, $TailCount)
    while (-not (Test-Path $Path)) {
      "[backend-file] waiting for $Path"
      Start-Sleep -Seconds 1
    }
    Get-Content -Path $Path -Tail $TailCount -Wait -ErrorAction Continue | ForEach-Object {
      "[backend-file] $_"
    }
  } @($BackendLog, $Tail)
}

if (-not $NoDebugApi) {
  $jobs += Start-LogJob "debug-api" {
    param($BaseUrl, $PollSeconds, $RunOnce)
    $seen = New-Object "System.Collections.Generic.HashSet[string]"
    do {
      try {
        $data = Invoke-RestMethod -Uri "$BaseUrl/devlink-debug/logs.json" -TimeoutSec 3
        $requests = @($data.requests)
        [array]::Reverse($requests)
        foreach ($item in $requests) {
          $created = [string]$item.created_at
          $key = "request|$created|$($item.method)|$($item.path)|$($item.status)|$($item.duration_ms)"
          if ($seen.Add($key)) {
            "[api-request] $($item.method) $($item.path) -> $($item.status) $($item.duration_ms)ms ip=$($item.remote_addr) user=$($item.user)"
          }
        }

        $errors = @($data.errors)
        [array]::Reverse($errors)
        foreach ($item in $errors) {
          $created = [string]$item.created_at
          $payload = ($item.payload | ConvertTo-Json -Compress -Depth 12)
          $key = "error|$created|$($item.method)|$($item.path)|$($item.status)|$payload"
          if ($seen.Add($key)) {
            "[api-error] $($item.method) $($item.path) -> $($item.status) ip=$($item.remote_addr) payload=$payload"
          }
        }
      } catch {
        "[debug-api] unable to poll $BaseUrl/devlink-debug/logs.json :: $($_.Exception.Message)"
      }
      if ($RunOnce) { break }
      Start-Sleep -Seconds $PollSeconds
    } while ($true)
  } @($BaseUrl, $PollSeconds, [bool]$Once)
}

if (-not $NoDocker) {
  if (Has-Command "docker") {
    $jobs += Start-LogJob "docker" {
      param($Root, $TailCount)
      Set-Location $Root
      docker compose logs -f --tail $TailCount 2>&1 | ForEach-Object {
        "[docker] $_"
      }
    } @($Root, $Tail)
  } else {
    Write-LogLine "[docker] docker command not found"
  }
}

if (-not $NoAdb) {
  if (Has-Command "adb") {
    $jobs += Start-LogJob "adb" {
      param($Raw)
      $devices = adb devices 2>&1
      if (-not (($devices | Select-String -Pattern "\tdevice").Matches.Count)) {
        "[adb] no Android device in adb devices"
        $devices | ForEach-Object { "[adb] $_" }
        return
      }
      if ($Raw) {
        adb logcat -v time 2>&1 | ForEach-Object { "[adb] $_" }
      } else {
        adb logcat -v time ReactNativeJS:V ReactNative:V Expo:V AndroidRuntime:E System.err:W "*:S" 2>&1 | ForEach-Object {
          "[adb] $_"
        }
      }
    } @([bool]$RawAndroid)
  } else {
    Write-LogLine "[adb] adb command not found"
  }
}

if (-not $NoCodexLogs) {
  $CodexRoot = Join-Path $env:USERPROFILE ".codex"
  if (Test-Path $CodexRoot) {
    $codexFiles = Get-ChildItem -Path $CodexRoot -Recurse -Filter "*.log" -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime -Descending |
      Select-Object -First 4
    foreach ($file in $codexFiles) {
      $jobs += Start-LogJob ("codex-" + $file.BaseName) {
        param($Path, $TailCount)
        $name = [System.IO.Path]::GetFileName($Path)
        Get-Content -Path $Path -Tail $TailCount -Wait -ErrorAction Continue | ForEach-Object {
          "[codex:$name] $_"
        }
      } @($file.FullName, $Tail)
    }
    if (-not $codexFiles) {
      Write-LogLine "[codex] no .log files found under $CodexRoot"
    }
  } else {
    Write-LogLine "[codex] $CodexRoot not found"
  }
}

if ($StartCli) {
  $jobs += Start-LogJob "cli" {
    param($Root)
    $cliDir = Join-Path $Root "apps\cli"
    Set-Location $cliDir
    $exe = Join-Path $cliDir ".venv\Scripts\devlink.exe"
    if (-not (Test-Path $exe)) {
      "[cli] missing $exe; run scripts\dev-cli.ps1 first"
      return
    }
    & $exe connect 2>&1 | ForEach-Object { "[cli] $_" }
  } @($Root)
}

if ($jobs.Count -eq 0) {
  Write-LogLine "[dev-logs] no log sources selected"
  exit 1
}

try {
  do {
    if ($Once) {
      Start-Sleep -Milliseconds 2000
    }
    foreach ($job in @($jobs)) {
      Receive-Job -Job $job -ErrorAction SilentlyContinue | ForEach-Object {
        Write-LogLine ([string]$_)
      }
      if ($job.State -in @("Failed", "Stopped", "Completed")) {
        $reason = if ($job.ChildJobs.Count -gt 0) { $job.ChildJobs[0].JobStateInfo.Reason } else { $null }
        if ($reason) {
          Write-LogLine "[dev-logs] job $($job.Name) ended: $reason"
        }
      }
    }
    if ($Once) { break }
    Start-Sleep -Milliseconds 250
  } while ($true)
} finally {
  foreach ($job in @($jobs)) {
    Stop-Job -Job $job -ErrorAction SilentlyContinue | Out-Null
    Remove-Job -Job $job -Force -ErrorAction SilentlyContinue | Out-Null
  }
  Write-LogLine "[dev-logs] stopped"
}
