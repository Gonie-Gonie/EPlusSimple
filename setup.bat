@echo off
setlocal EnableExtensions

:: ============================================================================
:: EPlusSimple setup wrapper
:: ============================================================================
::
:: Purpose:
::   Users usually run setup.bat from the repository root.
::   The actual setup logic is implemented in scripts\dev\setup.ps1 because
::   PowerShell handles downloads, zip extraction, and path discovery more
::   reliably than a large batch file.
::
:: Why keep this wrapper?
::   - Users can still double-click or run setup.bat.
::   - The wrapper bypasses the PowerShell execution policy only for this run.
::   - The main setup logic remains easier to maintain in setup.ps1.
::
:: Expected repository layout:
::   <repo root>\setup.bat
::   <repo root>\scripts\dev\setup.ps1
::   <repo root>\requirements.txt
::   <repo root>\src\
:: ============================================================================

set "ROOT_DIR=%~dp0"
set "SETUP_PS1=%ROOT_DIR%scripts\dev\setup.ps1"

if not exist "%SETUP_PS1%" (
    echo [ERROR] PowerShell setup script was not found:
    echo         %SETUP_PS1%
    echo.
    echo Expected location:
    echo         scripts\dev\setup.ps1
    echo.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SETUP_PS1%" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo ============================================================================
    echo  [ERROR] Runtime setup failed. Exit code: %EXIT_CODE%
    echo ============================================================================
    echo.
    pause
)

exit /b %EXIT_CODE%
