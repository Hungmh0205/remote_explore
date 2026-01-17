# @Title: Log Archiver
# @Description: Zips log files older than 7 days and deletes originals.
# @Color: gray

$LogDir = "logs" # Adjust if your app uses a different folder
$ArchiveDir = "logs/archive"
$DaysOld = 7

if (-not (Test-Path $LogDir)) {
    Write-Host "Log directory '$LogDir' not found. Creating it for demo..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    # Create a dummy log for testing
    "Dummy Log Content" | Out-File "$LogDir/old_app.log"
}

if (-not (Test-Path $ArchiveDir)) {
    New-Item -ItemType Directory -Force -Path $ArchiveDir | Out-Null
}

Write-Host "Scanning '$LogDir' for files older than $DaysOld days..." -ForegroundColor Yellow

$filesToArchive = Get-ChildItem -Path $LogDir -Filter "*.log" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$DaysOld) }

if ($filesToArchive.Count -eq 0) {
    Write-Host "No old logs found to archive." -ForegroundColor Green
    exit 0
}

$zipName = "Logs_Archive_$(Get-Date -Format 'yyyyMMdd_HHmmss').zip"
$zipPath = Join-Path $ArchiveDir $zipName

Write-Host "Archiving $($filesToArchive.Count) files to $zipName..." -ForegroundColor Cyan

Compress-Archive -Path $filesToArchive.FullName -DestinationPath $zipPath
if ($?) {
    Write-Host "Zip created successfully." -ForegroundColor Green
    Write-Host "Deleting original files..." -ForegroundColor Yellow
    $filesToArchive | Remove-Item -Force
    Write-Host "Cleanup Done." -ForegroundColor Green
}
else {
    Write-Host "Failed to create zip archive." -ForegroundColor Red
}
