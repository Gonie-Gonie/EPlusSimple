@echo off
set VERSION=0.4.4
set PROJECT_NAME=GRSimulator
set RELEASE_DIR=dist\%PROJECT_NAME%_v%VERSION%
set OUTPUT_ZIP=dist\%PROJECT_NAME%_v%VERSION%.zip

echo [1/3] Cleaning up previous build and creating release folder...
if exist "dist" rd /s /q "dist"
mkdir "%RELEASE_DIR%"

echo [2/3] Copying files for distribution...
xcopy /E /I /Q "venv"     "%RELEASE_DIR%\venv\"
xcopy /E /I /Q "src"      "%RELEASE_DIR%\src\"
xcopy /E /I /Q "launcher" "%RELEASE_DIR%\launcher\"
copy "run.bat"  "%RELEASE_DIR%\run.bat" > nul

:: Add src path to the ._pth file for distribution
findstr /C:"..\src" "%RELEASE_DIR%\venv\python312._pth" > nul
if not %errorlevel% equ 0 (
    echo ..\src >> "%RELEASE_DIR%\venv\python312._pth"
)

echo [3/3] Creating archive: %OUTPUT_ZIP%
rem Use the 7-Zip executable included in the 'tools' folder
"%~dp0tools\7z.exe" a -tzip "%OUTPUT_ZIP%" "%RELEASE_DIR%\*" > nul

echo.
echo ✅ Distribution packaging complete!
pause