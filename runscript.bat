@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================================
REM EPlusSimple script runner
REM ============================================================================
REM Location:
REM   /runscript.bat
REM
REM Usage:
REM   runscript <command> [args...]
REM
REM Examples:
REM   runscript setup
REM   runscript setup -Force
REM   runscript build-go
REM   runscript build-go -Tidy
REM   runscript release
REM   runscript release -SkipRegressionTest -SkipDocs
REM
REM Rule:
REM   First argument  = command name
REM   Other arguments = passed to the mapped PowerShell script
REM ============================================================================


REM ============================================================================
REM [1] Repository root
REM ============================================================================

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"


REM ============================================================================
REM [2] Command map
REM ============================================================================
REM Add new scripts here.
REM
REM Format:
REM   set "SCRIPT_<COMMAND_NAME>=%ROOT_DIR%\relative\path\to\script.ps1"
REM
REM Then add one IF line in [6] Command dispatch.
REM ============================================================================

set "SCRIPT_SETUP=%ROOT_DIR%\scripts\setup\setup.ps1"
set "SCRIPT_BUILD_GO=%ROOT_DIR%\scripts\dev\build-go.ps1"
set "SCRIPT_RELEASE=%ROOT_DIR%\scripts\release\release.ps1"


REM ============================================================================
REM [3] PowerShell executable and common options
REM ============================================================================

set "POWERSHELL_EXE=powershell.exe"
set "POWERSHELL_ARGS=-NoProfile -ExecutionPolicy Bypass"


REM ============================================================================
REM [4] Read command
REM ============================================================================

if "%~1"=="" (
    echo [ERROR] Command was not specified.
    echo Available commands: setup, build-go, release
    exit /b 1
)

set "COMMAND=%~1"
shift /1


REM ============================================================================
REM [5] Collect remaining arguments
REM ============================================================================
REM Important:
REM   Do not use %%* after SHIFT.
REM   In batch files, %%* can still expand to the original full argument list.
REM   That would pass the command name itself to the PowerShell script.
REM
REM This block rebuilds the remaining arguments after the first command argument
REM has been removed.
REM ============================================================================

set "SCRIPT_ARGS="

:COLLECT_ARGS
if "%~1"=="" goto DISPATCH_COMMAND

set "ARG=%~1"
set "ARG=!ARG:"=\"!"
set "SCRIPT_ARGS=!SCRIPT_ARGS! "!ARG!""

shift /1
goto COLLECT_ARGS


REM ============================================================================
REM [6] Command dispatch
REM ============================================================================

:DISPATCH_COMMAND

if /I "%COMMAND%"=="setup" (
    set "TARGET_SCRIPT=%SCRIPT_SETUP%"
    goto RUN_SCRIPT
)

if /I "%COMMAND%"=="build-go" (
    set "TARGET_SCRIPT=%SCRIPT_BUILD_GO%"
    goto RUN_SCRIPT
)

if /I "%COMMAND%"=="release" (
    set "TARGET_SCRIPT=%SCRIPT_RELEASE%"
    goto RUN_SCRIPT
)

echo [ERROR] Unknown command: %COMMAND%
echo Available commands: setup, build-go, release
exit /b 1


REM ============================================================================
REM [7] Run selected PowerShell script
REM ============================================================================

:RUN_SCRIPT

if not exist "%TARGET_SCRIPT%" (
    echo [ERROR] PowerShell script was not found:
    echo   %TARGET_SCRIPT%
    exit /b 1
)

pushd "%ROOT_DIR%"

%POWERSHELL_EXE% %POWERSHELL_ARGS% -File "%TARGET_SCRIPT%" %SCRIPT_ARGS%

set "EXIT_CODE=%ERRORLEVEL%"

popd

if not "%EXIT_CODE%"=="0" (
    echo.
    echo ============================================================================
    echo [ERROR] Script failed.
    echo Command : %COMMAND%
    echo Script  : %TARGET_SCRIPT%
    echo ExitCode: %EXIT_CODE%
    echo ============================================================================
    echo.
    exit /b %EXIT_CODE%
)

exit /b 0
