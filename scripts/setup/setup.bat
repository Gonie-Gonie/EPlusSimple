@echo off
setlocal EnableExtensions

:: ============================================================================
:: EPlusSimple setup wrapper
:: ============================================================================
:: This wrapper is located at:
::   scripts\setup\setup.bat
::
:: It calls:
::   scripts\setup\setup.ps1
::
:: Repository root is two levels above this file.
:: ============================================================================

set "SETUP_DIR=%~dp0"

for %%I in ("%SETUP_DIR%..\..") do set "ROOT_DIR=%%~fI"

set "SETUP_PS1=%SETUP_DIR%setup.ps1"

if not exist "%SETUP_PS1%" (
    echo [ERROR] PowerShell setup script was not found:
    echo %SETUP_PS1%
    echo.
    pause
    exit /b 1
)

pushd "%ROOT_DIR%"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SETUP_PS1%" %*

set "EXIT_CODE=%ERRORLEVEL%"

popd

if not "%EXIT_CODE%"=="0" (
    echo.
    echo ============================================================================
    echo [ERROR] Runtime setup failed. Exit code: %EXIT_CODE%
    echo ============================================================================
    echo.
    pause
)

exit /b %EXIT_CODE%