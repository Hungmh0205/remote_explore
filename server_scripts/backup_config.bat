@echo off
REM @Title: Backup Configs
REM @Description: Backups the 'app' folder to a Backup directory.
REM @Color: blue

echo Starting Backup...
set BACKUP_DIR=Backup_%date:~-4,4%%date:~-10,2%%date:~-7,2%
mkdir "%BACKUP_DIR%" 2>nul

echo Copying app folder...
xcopy app "%BACKUP_DIR%\app" /E /I /Y

echo.
echo Backup completed to folder: %BACKUP_DIR%
dir "%BACKUP_DIR%"
