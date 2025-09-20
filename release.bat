@echo off
set VERSION=0.4.4
set PROJECT_NAME=GRSimulator
set RELEASE_DIR=dist\%PROJECT_NAME%_v%VERSION%
set OUTPUT_ZIP=%~dp0dist\%PROJECT_NAME%_v%VERSION%.zip

echo [1/3] Cleaning up previous build and creating release folder...
if exist "dist" rd /s /q "dist"
mkdir "%RELEASE_DIR%"

echo [2/3] Copying files for distribution...
xcopy /E /I /Q "venv"     "%RELEASE_DIR%\venv\"
xcopy /E /I /Q "src"      "%RELEASE_DIR%\src\"
xcopy /E /I /Q "launcher" "%RELEASE_DIR%\launcher\"
copy "runGRsim.bat"       "%RELEASE_DIR%\runGRsim.bat" > nul

:: Add src path to the ._pth file for distribution
findstr /C:"..\src" "%RELEASE_DIR%\venv\python312._pth" > nul
if not %errorlevel% equ 0 (
    echo ..\src >> "%RELEASE_DIR%\venv\python312._pth"
)

echo [3/3] Creating archive: %OUTPUT_ZIP%
:: 압축할 폴더로 직접 이동
pushd "%RELEASE_DIR%"
:: 현재 폴더(.)의 모든 내용물을 압축 파일에 추가
"%~dp0tools\7z.exe" a -tzip "%OUTPUT_ZIP%" . > nul
:: 원래 위치로 복귀
popd

echo.
echo ✅ Distribution packaging complete!
pause