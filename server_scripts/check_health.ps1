# @Title: System Health Check
# @Description: Checks disk space, memory usage, and internet connectivity.
# @Color: green

Write-Host "--- System Health Report ---" -ForegroundColor Cyan
$date = Get-Date
Write-Host "Date: $date"

# 1. Disk Space
Write-Host "`n[ Disk Space ]" -ForegroundColor Yellow
Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='Free(GB)';E={"{0:N2}" -f ($_.Free/1GB)}}, @{N='Total(GB)';E={"{0:N2}" -f ($_.Used/1GB + $_.Free/1GB)}} | Format-Table -AutoSize

# 2. Memory
Write-Host "[ Memory ]" -ForegroundColor Yellow
$os = Get-CimInstance Win32_OperatingSystem
$total = "{0:N2}" -f ($os.TotalVisibleMemorySize / 1MB)
$free = "{0:N2}" -f ($os.FreePhysicalMemory / 1MB)
Write-Host "Total RAM: $total GB"
Write-Host "Free RAM:  $free GB"

# 3. Connectivity
Write-Host "`n[ Connectivity ]" -ForegroundColor Yellow
$ping = Test-Connection -ComputerName 8.8.8.8 -Count 2 -Quiet
if ($ping) {
    Write-Host "Internet (8.8.8.8): OK" -ForegroundColor Green
} else {
    Write-Host "Internet (8.8.8.8): Failed" -ForegroundColor Red
}

Write-Host "`n--- End Report ---"
