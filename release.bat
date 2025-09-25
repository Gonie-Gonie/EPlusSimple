@echo off
set VERSION=0.4.5
set PROJECT_NAME=GRSimulator
set RELEASE_DIR=dist\%PROJECT_NAME%_v%VERSION%
set OUTPUT_ZIP=%~dp0dist\%PROJECT_NAME%_v%VERSION%.zip


echo [1/5] Cleaning up previous build and creating release folder...
if exist "dist" rd /s /q "dist"

echo [2/5] Generating releaseinfo.tex...

:: 라텍스 컴파일러 지정
set LATEX_COMPILER=latexmk

:: 현재 날짜를 YYYY.MM.DD. 형식으로 설정
:: %date% 변수는 시스템 설정에 따라 형식이 다를 수 있으나, 보통 'YYYY-MM-DD' 형식을 따릅니다.
set YYYY=%date:~0,4%
set MM=%date:~5,2%
set DD=%date:~8,2%
set TODAY=%YYYY%.%MM%.%DD%.

:: releaseinfo.tex 파일 작성 (덮어쓰기)
(
    echo \newcommand{\releaseversion}{%VERSION%}
    echo \newcommand{\releasedate}{%TODAY%}
) > "docs\releaseinfo.tex"


echo [3/5] Building Engineering Reference...

:: latexmk는 .tex 파일이 있는 곳에서 실행하는 것이 가장 안정적입니다.
pushd docs

:: -pdf: PDF 파일을 생성합니다.
:: -outdir: 출력 폴더를 지정합니다. 최상위 폴더 기준이므로 ../dist/docs 입니다.
if not exist "..\dist\docs\EngineeringReference" mkdir "..\dist\docs\EngineeringReference"

%LATEX_COMPILER% -pdf -outdir=../dist/docs "mainER.tex"

set BUILD_ERROR=%errorlevel%
popd

:: 빠져나온 후에 저장된 errorlevel 값으로 성공/실패를 판정합니다.
if %BUILD_ERROR% neq 0 (
    echo [ERROR] LaTeX build failed. Please check the log file.
    pause
    exit /b
)
echo     ...Documentation build successful.


echo [4/5] Copying files for distribution...
mkdir "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%\docs"
xcopy /E /I /Q "venv"     "%RELEASE_DIR%\venv\"
xcopy /E /I /Q "src"      "%RELEASE_DIR%\src\"
xcopy /E /I /Q "launcher" "%RELEASE_DIR%\launcher\"
copy "runEngine.bat"        "%RELEASE_DIR%\runEngine.bat" > nul
copy "runExcelLauncher.bat" "%RELEASE_DIR%\runExcelLauncher.bat" > nul
copy "dist\docs\mainER.pdf" "%RELEASE_DIR%\docs\EngineeringReference.pdf" > nul

:: Add src path to the ._pth file for distribution
findstr /C:"..\src" "%RELEASE_DIR%\venv\python312._pth" > nul
if not %errorlevel% equ 0 (
    echo ..\src >> "%RELEASE_DIR%\venv\python312._pth"
)


echo [5/5] Creating archive: %OUTPUT_ZIP%
:: 압축할 폴더로 직접 이동
pushd "%RELEASE_DIR%"
:: 현재 폴더(.)의 모든 내용물을 압축 파일에 추가
"%~dp0tools\7z.exe" a -tzip "%OUTPUT_ZIP%" . > nul
:: 원래 위치로 복귀
popd

echo.
echo ✅ Distribution packaging complete!