# Find virtual environment (venv or .venv)
$venvPath = $null
if (Test-Path -Path ".\venv") {
    $venvPath = ".\venv"
} elseif (Test-Path -Path ".\.venv") {
    $venvPath = ".\.venv"
}

if (-not $venvPath) {
    Write-Host "Error: No virtual environment (venv or .venv) found in the current directory." -ForegroundColor Red
    exit 1
}

Write-Host "Found virtual environment at: $venvPath" -ForegroundColor Green

# Activate virtual environment if not already active
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"

if (-not (Test-Path -Path $activateScript)) {
    Write-Host "Error: Activate.ps1 not found in $venvPath\Scripts." -ForegroundColor Red
    exit 1
}

# Check if the current virtual environment is the one we found
# Convert-Path is used to get the full, canonical path for comparison
if ($env:VIRTUAL_ENV -ne (Convert-Path $venvPath)) {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    try {
        . $activateScript # Source the script to activate in the current session
        Write-Host "Virtual environment activated." -ForegroundColor Green
    } catch {
        Write-Host "Error activating virtual environment: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Virtual environment already active." -ForegroundColor Green
}

# Run linting commands
Write-Host "Running isort..." -ForegroundColor Cyan
isort .
if ($LASTEXITCODE -ne 0) {
    Write-Host "isort failed with exit code $LASTEXITCODE" -ForegroundColor Red
    # Optionally exit here or continue with other checks
}

Write-Host "Running ruff format..." -ForegroundColor Cyan
ruff format
if ($LASTEXITCODE -ne 0) {
    Write-Host "ruff format failed with exit code $LASTEXITCODE" -ForegroundColor Red
    # Optionally exit here or continue with other checks
}

Write-Host "Running ruff check --fix..." -ForegroundColor Cyan
ruff check --fix
if ($LASTEXITCODE -ne 0) {
    Write-Host "ruff check --fix failed with exit code $LASTEXITCODE" -ForegroundColor Red
    # Optionally exit here or continue with other checks
}

Write-Host "Linting process complete." -ForegroundColor Green
