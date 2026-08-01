$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host -ForegroundColor Cyan $Message
}

function Write-Pass {
    Write-Host -ForegroundColor Green "✓ Passed`n"
}

function Write-Fail {
    Write-Host -ForegroundColor Red "========================="
    Write-Host -ForegroundColor Red "❌ Verification Failed"
    Write-Host -ForegroundColor Red "Fix the errors before pushing."
    Write-Host -ForegroundColor Red "========================="
    exit 1
}

function Run-Step {
    param(
        [string]$Name,
        [string]$StepId,
        [scriptblock]$Command
    )
    Write-Step "[$StepId/11] $Name..."
    $global:LASTEXITCODE = 0
    & $Command
    if ($global:LASTEXITCODE -ne 0 -and $global:LASTEXITCODE -ne $null) {
        Write-Fail
    }
    Write-Pass
}

# Ensure we are in the root directory
$ScriptPath = $MyInvocation.MyCommand.Path
$RootDir = Split-Path (Split-Path $ScriptPath)
Set-Location $RootDir

try {
    Run-Step "Checking Node version" "1" { node --version }
    Run-Step "Checking Python version" "2" { python --version }
    Run-Step "Installing dependencies" "3" { 
        pnpm install
        python -m pip install -e ./apps/api[dev]
    }
    Run-Step "Ruff Linting" "4" { 
        Push-Location apps/api
        python -m ruff check .
        $global:LASTEXITCODE = $LASTEXITCODE
        Pop-Location
    }
    Run-Step "Ruff Formatting" "5" { 
        Push-Location apps/api
        python -m ruff format --check .
        $global:LASTEXITCODE = $LASTEXITCODE
        Pop-Location
    }
    Run-Step "MyPy Type Checking" "6" { 
        Push-Location apps/api
        python -m mypy src
        $global:LASTEXITCODE = $LASTEXITCODE
        Pop-Location
    }
    Run-Step "Pytest" "7" { 
        Push-Location apps/api
        python -m pytest
        $global:LASTEXITCODE = $LASTEXITCODE
        Pop-Location
    }
    Run-Step "Frontend Linting" "8" { 
        pnpm lint 
        $global:LASTEXITCODE = $LASTEXITCODE
    }
    Run-Step "Frontend Type Checking" "9" { 
        pnpm typecheck 
        $global:LASTEXITCODE = $LASTEXITCODE
    }
    Run-Step "Frontend Build" "10" { 
        pnpm build 
        $global:LASTEXITCODE = $LASTEXITCODE
    }
    Run-Step "Backend Startup Validation" "11" { 
        Push-Location apps/api
        python -c "from src.main import app"
        $global:LASTEXITCODE = $LASTEXITCODE
        Pop-Location
    }

    Write-Host -ForegroundColor Green "========================="
    Write-Host -ForegroundColor Green "✅ Verification Passed"
    Write-Host -ForegroundColor Green "Ready to Commit & Push"
    Write-Host -ForegroundColor Green "========================="
} catch {
    Write-Fail
}
