# STOP.ps1 and START.ps1 Improvements

## Issues Found

1. **Port Cleanup Mismatch**: STOP.ps1 only cleans port 8080, but system uses 8081
2. **Incomplete Process Matching**: API process detection doesn't match 8081 port usage
3. **Missing Force-Kill**: No aggressive port cleanup before starting services

## Recommended Changes

### 1. Fix STOP.ps1 Port Cleanup (Line 115-116)

**Current:**
```powershell
Free-Port -port 3000
Free-Port -port 8080
```

**Should be:**
```powershell
Free-Port -port 3000
Free-Port -port 8080
Free-Port -port 8081  # Add this line - the port actually used by API
```

### 2. Fix API Process Detection in STOP.ps1

**Current Stop-ApiIfRunning function (lines 971-984):**
```powershell
($_.CommandLine -match '--port\s+8080' -or $_.CommandLine -match '0\.0\.0\.0:8080')
```

**Should include:**
```powershell
($_.CommandLine -match '--port\s+8080' -or $_.CommandLine -match '0\.0\.0\.0:8080' -or 
 $_.CommandLine -match '--port\s+8081' -or $_.CommandLine -match '0\.0\.0\.0:8081')
```

### 3. Add Aggressive Port Cleanup to START.ps1

Add this function and call it before starting API:

```powershell
function Force-Kill-Port {
    param([int]$Port)
    try {
        Write-Log "Force-clearing port $Port of any lingering processes" "INFO"
        $listeners = netstat -ano | Select-String "LISTENING" | Select-String ":$Port "
        foreach ($line in $listeners) {
            $pid = ($line.ToString() -split '\s+')[-1]
            if ($pid -match '^\d+$') {
                Write-Log "Force-killing PID $pid holding port $Port" "INFO"
                Stop-Process -Id ([int]$pid) -Force -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Milliseconds 500  # Give time for port to be released
    } catch {
        Write-Log "Force port cleanup failed for $Port : $($_.Exception.Message)" "WARN"
    }
}
```

### 4. Enhanced PID Tracking Cleanup

**Current issue:** PID tracking file can get stale
**Fix:** Add validation to ensure PIDs in tracking file are actually our processes

```powershell
function Stop-TrackedProcesses-Enhanced {
    if (-not (Test-Path $PidTrackingFile)) {
        Write-Log "No PID tracking file found" "INFO"
        return
    }
    
    try {
        $pidData = Get-Content $PidTrackingFile -Raw | ConvertFrom-Json
        $killedCount = 0
        
        foreach ($key in ($pidData | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name)) {
            $processPid = $pidData.$key
            try {
                $process = Get-Process -Id $processPid -ErrorAction SilentlyContinue
                if ($process) {
                    # Verify it's actually our process by checking command line
                    $wmi = Get-CimInstance Win32_Process -Filter "ProcessId=$processPid" -ErrorAction SilentlyContinue
                    if ($wmi -and ($wmi.CommandLine -match 'uvicorn' -or $wmi.CommandLine -match 'src\.main:app')) {
                        Write-Log "Stopping tracked process: $key (PID: $processPid)" "INFO"
                        Stop-Process -Id $processPid -Force -ErrorAction SilentlyContinue
                        $killedCount++
                    } else {
                        Write-Log "PID $processPid is not our process, skipping" "INFO"
                    }
                }
            } catch {
                Write-Log "Failed to stop tracked process $key (PID: $processPid): $($_.Exception.Message)" "WARN"
            }
        }
        
        # Always clear the tracking file
        "{}" | Set-Content $PidTrackingFile
        Write-Log "Stopped $killedCount tracked processes" "INFO"
    } catch {
        Write-Log "Failed to process PID tracking file: $($_.Exception.Message)" "ERROR"
    }
}
```

## Implementation Priority

1. **HIGH**: Fix STOP.ps1 to clean port 8081 (1 line change)
2. **HIGH**: Add Force-Kill-Port function to START.ps1 and call before API start
3. **MEDIUM**: Update API process detection patterns to include 8081
4. **LOW**: Enhance PID tracking validation

## Quick Fix for Immediate Problem

Add this line to STOP.ps1 after line 115:
```powershell
Free-Port -port 8081
```

This single change will prevent the port conflict issue from recurring.