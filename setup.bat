@echo off
setlocal

:: ============================================================================
::                            [ 설정 변수 ]
:: ============================================================================
set PYTHON_VERSION_SHORT=312
set PYTHON_VERSION_FULL=3.12.7
set PYTHON_DIR=python-portable
set PYTHON_ZIP_FILENAME=python-%PYTHON_VERSION_FULL%-embed-amd64.zip
set PYTHON_DOWNLOAD_URL=https://www.python.org/ftp/python/%PYTHON_VERSION_FULL%/%PYTHON_ZIP_FILENAME%
set GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py

:: ============================================================================

set PTH_FILE=.\%PYTHON_DIR%\python%PYTHON_VERSION_SHORT%._pth
set SRC_PATH=..\src

echo [1/5] Portable Python 환경을 확인합니다...
if exist "%PYTHON_DIR%\" (
    echo     ...이미 '%PYTHON_DIR%' 폴더가 존재합니다. 다운로드를 건너뜁니다.
    goto :InstallPackages
)

echo [2/5] Portable Python %PYTHON_VERSION_FULL% 버전을 다운로드합니다...
curl -L -o %PYTHON_ZIP_FILENAME% %PYTHON_DOWNLOAD_URL%
if %errorlevel% neq 0 (
    echo [오류] 다운로드에 실패했습니다.
    pause
    exit /b
)

echo [3/5] 다운로드한 파일의 압축을 해제합니다...
mkdir %PYTHON_DIR%
tar -xf %PYTHON_ZIP_FILENAME% -C %PYTHON_DIR%
if %errorlevel% neq 0 (
    echo [오류] 압축 해제에 실패했습니다.
    pause
    exit /b
)
del %PYTHON_ZIP_FILENAME%

:InstallPackages
echo [4/5] pip를 설치합니다...
curl -L -o get-pip.py %GET_PIP_URL%
if %errorlevel% neq 0 (
    echo [오류] get-pip.py 다운로드에 실패했습니다.
    pause
    exit /b
)
.\%PYTHON_DIR%\python.exe get-pip.py
del get-pip.py
echo     ...pip 설치 완료!

echo [5/5] 패키지 설치 및 경로 설정을 진행합니다...
call :DoSetup
goto :eof

:DoSetup
    echo     (a) requirements.txt 패키지를 설치합니다...
    .\%PYTHON_DIR%\Scripts\pip.exe install -r requirements.txt

    echo     (b) '%PTH_FILE%' 파일에 src 경로를 추가합니다...
    findstr /C:"%SRC_PATH%" "%PTH_FILE%" > nul
    if %errorlevel% equ 0 (
        echo         ...이미 경로가 설정되어 있습니다.
    ) else (
        echo %SRC_PATH% >> "%PTH_FILE%"
        echo         ...src 경로를 추가했습니다.
    )
    goto :eof

:eof
echo.
echo ============================================================================
echo  ✅ 모든 개발 환경 설정이 완료되었습니다!
echo ============================================================================
echo.
pause