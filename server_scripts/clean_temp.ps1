# @Title: Clean Temp Files
# @Description: Deletes files in %TEMP% and clears Recycle Bin.
# @Color: red

$TempPath = [System.IO.Path]::GetTempPath()
Write-Host "Cleaning Temp Folder: $TempPath" -ForegroundColor Yellow

try {
    Get-ChildItem -Path $TempPath -Recurse -Force -ErrorAction SilentlyContinue | 
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-1) } | 
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Cleaned old temp files." -ForegroundColor Green
} catch {
    Write-Host "Some files could not be deleted (in use)." -ForegroundColor Gray
}

Write-Host "`nCleaning Recycle Bin..." -ForegroundColor Yellow
# Note: Clear-RecycleBin requires user interaction usually, forcing it:
# Only works if run as Admin and supported by OS version in automation context
try {
    # This might fail in some non-interactive shells, safely skip if so
    Clear-RecycleBin -Force -ErrorAction SilentlyContinue
    Write-Host "Recycle bin emptied." -ForegroundColor Green
} catch {
    Write-Host "Could not empty recycle bin (might be empty or permission issue)." -ForegroundColor Gray
}

Write-Host "Done."
