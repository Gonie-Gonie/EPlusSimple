@echo off
setlocal

:: ============================================================================
::                            [ Configuration ]
::  To change the Python version, only modify the variables in this section.
:: ============================================================================
set PYTHON_VERSION_SHORT=312
set PYTHON_VERSION_FULL=3.12.7
set PYTHON_DIR=venv
set PYTHON_ZIP_FILENAME=python-%PYTHON_VERSION_FULL%-embed-amd64.zip
set PYTHON_DOWNLOAD_URL=https://www.python.org/ftp/python/%PYTHON_VERSION_FULL%/%PYTHON_ZIP_FILENAME%
set GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py

:: ============================================================================

set PTH_FILE=.\%PYTHON_DIR%\python%PYTHON_VERSION_SHORT%._pth
set SRC_PATH=..\src

echo [1/5] Checking for existing Python environment...
if exist "%PYTHON_DIR%\" (
    echo     ...Found '%PYTHON_DIR%' directory. Skipping download.
    goto :InstallPackages
)

echo [2/5] Downloading Portable Python %PYTHON_VERSION_FULL%...
curl -L -o %PYTHON_ZIP_FILENAME% %PYTHON_DOWNLOAD_URL%
if %errorlevel% neq 0 (
    echo [ERROR] Download failed. Check the URL or your network connection.
    pause
    exit /b
)

echo [3/5] Extracting downloaded files...
mkdir %PYTHON_DIR%
tar -xf %PYTHON_ZIP_FILENAME% -C %PYTHON_DIR%
if %errorlevel% neq 0 (
    echo [ERROR] Extraction failed.
    pause
    exit /b
)
del %PYTHON_ZIP_FILENAME%

:InstallPackages
echo [4/5] Installing pip...
curl -L -o get-pip.py %GET_PIP_URL%
if %errorlevel% neq 0 (
    echo [ERROR] Failed to download get-pip.py.
    pause
    exit /b
)
.\%PYTHON_DIR%\python.exe get-pip.py
del get-pip.py
echo     ...pip installation complete!

echo [5/5] Installing packages and setting up paths...
call :DoSetup
goto :eof

:DoSetup
    echo     (a) Installing packages from requirements.txt...
    .\%PYTHON_DIR%\Scripts\pip.exe install -r requirements.txt

    echo     (b) Adding src path to '%PTH_FILE%'...
    findstr /C:"%SRC_PATH%" "%PTH_FILE%" > nul
    if %errorlevel% equ 0 (
        echo         ...Path already exists.
    ) else (
        echo %SRC_PATH% >> "%PTH_FILE%"
        echo         ...src path added successfully.
    )
    goto :eof

:eof
echo.
echo ============================================================================
echo  ^>^> All development environment setup is complete! ^<^<
echo ============================================================================
echo.
pause