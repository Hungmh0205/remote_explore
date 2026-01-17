# @Title: Auto Update App (CI/CD)
# @Description: Pulls code from 'main' branch and installs dependencies.
# @Color: blue

Write-Host "--- Mini CI/CD Pipeline ---" -ForegroundColor Cyan

# 1. Check Git Branch
$branch = git rev-parse --abbrev-ref HEAD
Write-Host "Current Branch: $branch" -ForegroundColor Yellow

if ($branch.Trim() -ne "main") {
    Write-Host "Error: You are not on the 'main' branch. Auto-update is restricted to 'main' only." -ForegroundColor Red
    exit 1
}

# 2. Pull Code
Write-Host "`nPulling latest code from origin/main..." -ForegroundColor Yellow
git pull origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "Git pull failed." -ForegroundColor Red
    exit 1
}

# 3. Check requirements
if (Test-Path "requirements.txt") {
    Write-Host "`nChecking dependencies..." -ForegroundColor Yellow
    # Assuming venv is active or we are running in the python env
    pip install -r requirements.txt
}

Write-Host "`nUpdate Complete!" -ForegroundColor Green
Write-Host "Note: If code files changed, the Uvicorn server should reload automatically." -ForegroundColor Gray
