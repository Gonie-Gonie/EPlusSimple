@echo off
setlocal EnableExtensions

REM ============================================================================
REM EPlusSimple release wrapper
REM ============================================================================
REM
REM Purpose
REM   Keep the user-facing entry point as a .bat file, while moving the actual
REM   release logic to PowerShell.
REM
REM Expected location
REM   scripts\dev\release.bat
REM   scripts\dev\release.ps1
REM
REM Typical usage
REM   scripts\dev\release.bat
REM   scripts\dev\release.bat --for reb
REM   scripts\dev\release.bat --for kalis
REM
REM Notes
REM   - This wrapper supports the legacy "--for reb" style.
REM   - For advanced options, call release.ps1 directly or extend the
REM     argument mapping below.
REM ============================================================================

set "SCRIPT_DIR=%~dp0"
set "RELEASE_PS1=%SCRIPT_DIR%release.ps1"

if not exist "%RELEASE_PS1%" (
    echo [ERROR] PowerShell release script was not found:
    echo         %RELEASE_PS1%
    echo.
    echo Expected location:
    echo         scripts\dev\release.ps1
    echo.
    pause
    exit /b 1
)

set "BUILD_FOR="
set "VERSION="
set "PS_ARGS="

:PARSE_ARGS
if "%~1"=="" goto RUN_RELEASE

if /I "%~1"=="--for" (
    if "%~2"=="" (
        echo [ERROR] Missing value after --for. Use "kalis" or "reb".
        pause
        exit /b 1
    )
    set "BUILD_FOR=%~2"
    shift
    shift
    goto PARSE_ARGS
)

if /I "%~1"=="-for" (
    if "%~2"=="" (
        echo [ERROR] Missing value after -for. Use "kalis" or "reb".
        pause
        exit /b 1
    )
    set "BUILD_FOR=%~2"
    shift
    shift
    goto PARSE_ARGS
)

if /I "%~1"=="-BuildFor" (
    if "%~2"=="" (
        echo [ERROR] Missing value after -BuildFor. Use "kalis" or "reb".
        pause
        exit /b 1
    )
    set "BUILD_FOR=%~2"
    shift
    shift
    goto PARSE_ARGS
)

if /I "%~1"=="--version" (
    if "%~2"=="" (
        echo [ERROR] Missing value after --version.
        pause
        exit /b 1
    )
    set "VERSION=%~2"
    shift
    shift
    goto PARSE_ARGS
)

if /I "%~1"=="-Version" (
    if "%~2"=="" (
        echo [ERROR] Missing value after -Version.
        pause
        exit /b 1
    )
    set "VERSION=%~2"
    shift
    shift
    goto PARSE_ARGS
)

if /I "%~1"=="--skip-regression" (
    set "PS_ARGS=%PS_ARGS% -SkipRegressionTest"
    shift
    goto PARSE_ARGS
)

if /I "%~1"=="-SkipRegressionTest" (
    set "PS_ARGS=%PS_ARGS% -SkipRegressionTest"
    shift
    goto PARSE_ARGS
)

if /I "%~1"=="--skip-docs" (
    set "PS_ARGS=%PS_ARGS% -SkipDocs"
    shift
    goto PARSE_ARGS
)

if /I "%~1"=="-SkipDocs" (
    set "PS_ARGS=%PS_ARGS% -SkipDocs"
    shift
    goto PARSE_ARGS
)

if /I "%~1"=="--no-clean" (
    set "PS_ARGS=%PS_ARGS% -NoClean"
    shift
    goto PARSE_ARGS
)

if /I "%~1"=="-NoClean" (
    set "PS_ARGS=%PS_ARGS% -NoClean"
    shift
    goto PARSE_ARGS
)

REM Unknown arguments are passed through as-is.
set "PS_ARGS=%PS_ARGS% %~1"
shift
goto PARSE_ARGS

:RUN_RELEASE

set "CMD_ARGS="

if defined BUILD_FOR (
    set "CMD_ARGS=%CMD_ARGS% -BuildFor %BUILD_FOR%"
)

if defined VERSION (
    set "CMD_ARGS=%CMD_ARGS% -Version %VERSION%"
)

set "CMD_ARGS=%CMD_ARGS%%PS_ARGS%"

powershell.exe ^
    -NoProfile ^
    -ExecutionPolicy Bypass ^
    -File "%RELEASE_PS1%" %CMD_ARGS%

set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo ============================================================================
    echo  [ERROR] Release failed. Exit code: %EXIT_CODE%
    echo ============================================================================
    echo.
    pause
    exit /b %EXIT_CODE%
)

echo.
echo ============================================================================
echo  Release completed successfully.
echo ============================================================================
echo.
pause
exit /b 0
