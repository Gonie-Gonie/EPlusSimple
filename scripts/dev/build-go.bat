@echo off
chcp 65001 > nul

REM ----------------------------------------------------------------------------
REM EPlusSimple Go build wrapper
REM ----------------------------------------------------------------------------

SET "SCRIPT_DIR=%~dp0"
SET "PS_SCRIPT=%SCRIPT_DIR%build-go.ps1"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*

IF ERRORLEVEL 1 (
    echo.
    echo [ERROR] Go build failed.
    exit /b %ERRORLEVEL%
)

echo.
echo [OK] Go build completed.