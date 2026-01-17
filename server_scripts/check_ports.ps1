# @Title: Port Inspector
# @Description: Lists open TCP/UDP ports and the process using them.
# @Color: purple

Write-Host "--- Listening Ports ---" -ForegroundColor Cyan

# Get TCP Connections that are in 'Listen' state
$connections = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue

$results = foreach ($conn in $connections) {
    try {
        $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        [PSCustomObject]@{
            Port        = $conn.LocalPort
            Protocol    = "TCP"
            PID         = $conn.OwningProcess
            ProcessName = if ($process) { $process.ProcessName } else { "System/Unknown" }
        }
    }
    catch {
        # Ignore errors mapping process
    }
}

# Sort by Port and Display
$results | Sort-Object Port | Format-Table -AutoSize

Write-Host "Note: To see more details, run as Administrator." -ForegroundColor Gray
