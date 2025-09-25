@echo off
setlocal

:: ============================================================================
::                            [ Configuration ]
:: ============================================================================

:: Python
set PYTHON_VERSION_SHORT=312
set PYTHON_VERSION_FULL=3.12.7
set PYTHON_DIR=venv
set PYTHON_ZIP_FILENAME=python-%PYTHON_VERSION_FULL%-embed-amd64.zip
set PYTHON_DOWNLOAD_URL=https://www.python.org/ftp/python/%PYTHON_VERSION_FULL%/%PYTHON_ZIP_FILENAME%

:: pip
set GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py

:: 7zip
set TOOLS_DIR=tools
set SEVENZIP_DOWNLOAD_URL=https://7-zip.org/a/7z2407-extra.zip
set SEVENZIP_ZIP_FILENAME=7z2407-extra.zip

:: ============================================================================

set PTH_FILE=.\%PYTHON_DIR%\python%PYTHON_VERSION_SHORT%._pth
set SRC_PATH=..\src

echo [1/6] Checking for existing Python environment...
if exist "%PYTHON_DIR%\" (
    echo     ...Found '%PYTHON_DIR%' directory. Skipping download.
    goto :InstallPackages
)

echo [2/6] Downloading Portable Python %PYTHON_VERSION_FULL%...
curl -L -o %PYTHON_ZIP_FILENAME% %PYTHON_DOWNLOAD_URL%
if %errorlevel% neq 0 (
    echo [ERROR] Download failed.
    pause
    exit /b
)

echo [3/6] Extracting downloaded files...
mkdir %PYTHON_DIR%
tar -xf %PYTHON_ZIP_FILENAME% -C %PYTHON_DIR%
if %errorlevel% neq 0 (
    echo [ERROR] Extraction failed.
    pause
    exit /b
)
del %PYTHON_ZIP_FILENAME%

:InstallPackages
echo [4/6] Installing pip and enabling site-packages...
curl -L -o get-pip.py %GET_PIP_URL%
if %errorlevel% neq 0 (
    echo [ERROR] Failed to download get-pip.py.
    pause
    exit /b
)

:: Run get-pip.py to install pip
.\%PYTHON_DIR%\python.exe get-pip.py
del get-pip.py

:: *** NEW STEP: Add site-packages path to ._pth file ***
echo     ...Configuring environment paths.
(echo Lib\site-packages) >> "%PTH_FILE%"

echo     ...pip installation and configuration complete!

echo [5/6] Installing packages and setting up paths...
call :DoSetup
goto :eof

:DoSetup
    echo     (a) Installing build tools...
    .\%PYTHON_DIR%\Scripts\pip.exe install setuptools wheel

    echo     (b) Installing packages from requirements.txt...
    .\%PYTHON_DIR%\Scripts\pip.exe install -r requirements.txt

    echo     (c) Adding src path to '%PTH_FILE%'...

    findstr /C:"%SRC_PATH%" "%PTH_FILE%" > nul
    if %errorlevel% equ 0 (
        echo         ...Path already exists.
    ) else (
        echo %SRC_PATH% >> "%PTH_FILE%"
        echo         ...src path added successfully.
    )
    goto :eof

:eof

echo [6/6] Checking for 7-Zip...
if exist "%TOOLS_DIR%\7z.exe" (
    echo     ...Found 7z.exe. Skipping download.
) else (
    echo     ...7-Zip not found. Downloading...
    if not exist "%TOOLS_DIR%" mkdir %TOOLS_DIR%
    
    curl -L -o %SEVENZIP_ZIP_FILENAME% %SEVENZIP_DOWNLOAD_URL%
    if %errorlevel% neq 0 (
        echo [ERROR] 7-Zip download failed.
        pause
        exit /b
    )
    
    echo     ...Extracting 7-Zip to '%TOOLS_DIR%'.
    powershell -Command "Expand-Archive -Path '%SEVENZIP_ZIP_FILENAME%' -DestinationPath '%TOOLS_DIR%' -Force"
    if %errorlevel% neq 0 (
        echo [ERROR] 7-Zip extraction failed.
        echo Please ensure PowerShell is available to extract files.
        pause
        exit /b
    )
    
    del %SEVENZIP_ZIP_FILENAME%
    echo     ...7-Zip setup complete.
)

echo.
echo ============================================================================
echo  ^>^> All development environment setup is complete! ^<^<
echo ============================================================================
echo.
pause