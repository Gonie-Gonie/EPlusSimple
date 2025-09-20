@echo off
set VERSION=1.0.0
set PROJECT_NAME=GRSimulator
set RELEASE_DIR=dist\%PROJECT_NAME%_v%VERSION%
set OUTPUT_ZIP=dist\%PROJECT_NAME%_v%VERSION%.zip

echo [1/3] 이전 빌드를 정리하고 배포 폴더를 생성합니다...
if exist "dist" rd /s /q "dist"
mkdir "%RELEASE_DIR%"

echo [2/3] 배포할 파일들을 복사합니다...
xcopy /E /I /Q "venv"     "%RELEASE_DIR%\venv\"
xcopy /E /I /Q "src"      "%RELEASE_DIR%\src\"
xcopy /E /I /Q "launcher" "%RELEASE_DIR%\launcher\"
xcopy /E /I /Q "run.bat"  "%RELEASE_DIR%\run.bat"

:: 2. 배포용 ._pth 파일에 src 경로 추가 (개발용과 동일한 로직)
findstr /C:"..\src" "%RELEASE_DIR%\python-portable\python312._pth" > nul
if not %errorlevel% equ 0 (
    echo ..\src >> "%RELEASE_DIR%\python-portable\python312._pth"
)

echo [3/3] 압축 파일을 생성합니다: %OUTPUT_ZIP%
7z a -tzip "%OUTPUT_ZIP%" "%RELEASE_DIR%" > nul

echo.
echo ✅ 배포 패키징 완료!
pause