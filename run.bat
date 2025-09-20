@echo off
REM -----------------------------------------
REM My Python Module 실행 스크립트
REM -----------------------------------------

:: 사용법: mymodule.bat [인자값] --옵션 [옵션값]

REM --- 설정 변수 ---
SET "BATCH_DIR=%~dp0"
SET "PYTHON_EXE=%BATCH_DIR%venv\python.exe"
SET "MODULE_PATH=%BATCH_DIR%src\pyGRsim"
SET "LOG_FILE=%BATCH_DIR%log.log"

REM --- 기존 로그 파일 삭제 ---
IF EXIST "%LOG_FILE%" (
    ECHO 기존 로그 파일(%LOG_FILE%)을 삭제합니다.
    DEL "%LOG_FILE%"
)

ECHO.
ECHO 파이썬 스크립트를 실행합니다...
ECHO 로그는 %LOG_FILE% 파일에 저장됩니다.
ECHO.

REM --- 파이썬 스크립트 실행 및 로그 저장 ---
REM 전달된 모든 인자를 넘겨 실행하고, 표준 출력과 표준 오류를 모두 로그 파일에 기록
"%PYTHON_EXE%" "%MODULE_PATH%" %* > "%LOG_FILE%" 2>&1

ECHO.
ECHO 스크립트 실행이 완료되었습니다.
pause