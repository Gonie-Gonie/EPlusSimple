@echo off
chcp 65001 > nul
REM -----------------------------------------
REM My Python Module Execution Script
REM -----------------------------------------

:: Usage: mymodule.bat [argument] --option [value]

REM --- Configuration Variables ---
SET "BATCH_DIR=%~dp0"
SET "PYTHON_EXE=%BATCH_DIR%venv\python.exe"
SET "MODULE_NAME=pyGRsim"
SET "LOG_FILE=%BATCH_DIR%log.log"

REM --- Delete existing log file ---
IF EXIST "%LOG_FILE%" (
    ECHO Deleting existing log file: %LOG_FILE%
    DEL "%LOG_FILE%"
)

ECHO.
ECHO Executing Python script...
ECHO Log will be saved to: %LOG_FILE%
ECHO.

REM --- Execute Python script and save log ---
REM Pass all arguments and redirect both stdout and stderr to the log file
"%PYTHON_EXE%" -m "%MODULE_NAME%" %* > "%LOG_FILE%" 2>&1

ECHO.
ECHO Script execution finished.