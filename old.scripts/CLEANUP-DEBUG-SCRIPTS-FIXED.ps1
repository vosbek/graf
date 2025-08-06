param()

Write-Host "=== GRAPHRAG PRODUCTION HARDENING - SCRIPT CLEANUP ===" -ForegroundColor Yellow
Write-Host ""

# Essential scripts to KEEP
$essentialScripts = @(
    "CLEAN-RESTART-V2.ps1",
    "STOP.ps1", 
    "HEALTH-CHECK.ps1",
    "CLEANUP-DEBUG-SCRIPTS.ps1",
    "CLEANUP-DEBUG-SCRIPTS-FIXED.ps1"
)

# Get all PowerShell scripts except essential ones
$allScripts = Get-ChildItem -Path "." -Filter "*.ps1" | Where-Object { $_.Name -notin $essentialScripts }

Write-Host "Essential scripts to keep:" -ForegroundColor Green
foreach ($script in $essentialScripts) {
    if (Test-Path $script) {
        Write-Host "  checkmark $script" -ForegroundColor White
    }
}
Write-Host ""

if ($allScripts.Count -gt 0) {
    Write-Host "Debug/temporary scripts to remove ($($allScripts.Count)):" -ForegroundColor Yellow
    foreach ($script in $allScripts) {
        Write-Host "  - $($script.Name)" -ForegroundColor Gray
    }
    Write-Host ""
    
    $confirm = Read-Host "Remove these $($allScripts.Count) debug scripts? (y/N)"
    
    if ($confirm -eq 'y' -or $confirm -eq 'Y') {
        Write-Host "Removing debug scripts..." -ForegroundColor Cyan
        foreach ($script in $allScripts) {
            try {
                Remove-Item $script.FullName -Force
                Write-Host "  checkmark Removed $($script.Name)" -ForegroundColor Green
            }
            catch {
                Write-Host "  X Failed to remove $($script.Name): $($_.Exception.Message)" -ForegroundColor Red
            }
        }
        Write-Host ""
        Write-Host "Cleanup completed!" -ForegroundColor Green
    }
    else {
        Write-Host "Cleanup cancelled." -ForegroundColor Yellow
    }
}
else {
    Write-Host "No debug scripts found to remove." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== HARDENED SCRIPT SET ===" -ForegroundColor Green
Write-Host "Your GraphRAG system now has a minimal, production-ready script set:" -ForegroundColor White
Write-Host ""
Write-Host "CLEAN-RESTART-V2.ps1  - Complete system restart with v2 architecture" -ForegroundColor Cyan
Write-Host "STOP.ps1              - Safe shutdown with PID tracking" -ForegroundColor Cyan  
Write-Host "HEALTH-CHECK.ps1      - Quick health status verification" -ForegroundColor Cyan
Write-Host ""
Write-Host "Usage:" -ForegroundColor Yellow
Write-Host "  .\CLEAN-RESTART-V2.ps1  # Start the system"
Write-Host "  .\HEALTH-CHECK.ps1      # Check if it's working"  
Write-Host "  .\STOP.ps1             # Stop the system"
Write-Host ""