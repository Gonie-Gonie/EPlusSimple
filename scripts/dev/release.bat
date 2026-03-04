@echo off
set "VERSION=0.6.1"

:: ------------------------------------------------------------------------ ::
::                          DIR & PATH SETUP                                ::
:: ------------------------------------------------------------------------ ::
:: 현재 스크립트 위치(scripts\dev\)에서 두 단계 위로 올라가 최상위(Root) 경로를 구함
set "ROOT_DIR=%~dp0..\.."
:: 작업 디렉토리를 프로젝트 최상위로 강제 이동
cd /d "%ROOT_DIR%"

:: 이제부터 모든 상대 경로(dist, docs, venv 등)는 최상위 폴더 기준으로 정상 작동합니다.

:: ------------------------------------------------------------------------ ::
::                           BUILD TARGET                                   ::
:: ------------------------------------------------------------------------ ::
::
:: By default, build for "kalis"
:: Use: release.bat --for reb (to build for "reb")
::
set "BUILD_FOR=kalis"
if /I "%1" == "--for" (
    if /I "%2" == "reb" (
        set "BUILD_FOR=reb"
    ) else if /I "%2" == "kalis" (
        set "BUILD_FOR=kalis"
    ) else (
        echo [ERROR] Invalid build target specified for --for. Use 'kalis' or 'reb'.
        pause
        exit /b 1
    )
)

:: Update project name and paths based on build target
set "PROJECT_NAME=EPlusSimple"
set "VERSION_SUFFIX="

if /I "%BUILD_FOR%" == "reb" (
    set "VERSION_SUFFIX=R"
)

set "VERSION_STRING=V%VERSION%%VERSION_SUFFIX%"
set "RELEASE_DIR=dist\%PROJECT_NAME%_%VERSION_STRING%"
set "OUTPUT_ZIP=%CD%\dist\%PROJECT_NAME%_%VERSION_STRING%.zip"
set "FINAL_PROJECT_NAME=%PROJECT_NAME%_%VERSION_STRING%"

echo ======================================================
echo Building EPlusSimple %VERSION_STRING% for [%BUILD_FOR%]
echo ======================================================
echo.



echo [1/5] Cleaning up previous build and creating release directory...
if exist "dist" rd /s /q "dist"

:: Create release directory
echo ...Build target: %BUILD_FOR%
mkdir "%RELEASE_DIR%"

:: Copy common files
xcopy /E /I /Q "venv"     "%RELEASE_DIR%\venv\"
xcopy /E /I /Q "examples" "%RELEASE_DIR%\examples\"
copy "runEngine.bat"        "%RELEASE_DIR%\runEngine.bat" > nul
copy "runExcelLauncher.bat" "%RELEASE_DIR%\runExcelLauncher.bat" > nul



echo [2/5] Generating Regression Test Result...

echo Running Regression Tests before building report...
venv\python.exe scripts\dev\regressiontest.py > regtest.log 2>&1

if %errorlevel% neq 0 (
    echo [ERROR] Regression test failed! Aborting release.
    pause
    exit /b 1
)



echo [3/5] Generating documentations...

:: 라텍스 컴파일러 지정
set "LATEX_COMPILER=latexmk"

:: 현재 날짜를 YYYY.MM.DD.형식으로 설정
:: %date% 변수는 시스템 설정에 따라 형식이 다를 수 있으나, 보통 'YYYY-MM-DD' 형식을 따릅니다.
set "YYYY=%date:~0,4%"
set "MM=%date:~5,2%"
set "DD=%date:~8,2%"
set "TODAY=%YYYY%.%MM%.%DD%."
:: releaseinfo.tex 파일 작성 (덮어쓰기)
(
    echo \newcommand{\releaseversion}{%VERSION_STRING%}
    echo \newcommand{\releasedate}{%TODAY%}
) > "docs\releaseinfo.tex"

@echo off
setlocal enabledelayedexpansion

:: 문서 리스트 정의: "파일이름(확장자제외)" "출력될표시이름"
call :BuildAndCopy "mainTRM"  "Technical Reference Manual"
call :BuildAndCopy "mainRTR"  "Regression Test Report"
call :BuildAndCopy "mainRN"   "Release Note"



echo [4/5] Copying source files and setting up configuration...

:: 1. 공통 src 모듈 복사 (항상 복사되는 것들)
echo     ...Copying common src modules...
mkdir "%RELEASE_DIR%\src"
xcopy /E /I /Q "src\epsimple" "%RELEASE_DIR%\src\epsimple\"
xcopy /E /I /Q "src\idragon"  "%RELEASE_DIR%\src\idragon\"

:: 2. launcher 공통 파일 복사
echo     ...Copying common launcher files...
mkdir "%RELEASE_DIR%\src\launcher"
xcopy /E /I /Q "src\launcher\static" "%RELEASE_DIR%\src\launcher\static\"
copy "src\launcher\__init__.py" "%RELEASE_DIR%\src\launcher\__init__.py" > nul
copy "src\launcher\__main__.py" "%RELEASE_DIR%\src\launcher\__main__.py" > nul


if /I "%BUILD_FOR%"=="kalis" goto :CFG_KALIS
if /I "%BUILD_FOR%"=="reb"   goto :CFG_REB
echo [ERROR] BUILD_FOR is invalid: [%BUILD_FOR%]
exit /b 1

:CFG_KALIS
echo     ...Configuring for [KALIS]...
:: Kalis 전용 launcher 파일 복사
xcopy /E /I /Q "src\launcher\templates" "%RELEASE_DIR%\src\launcher\templates\"
copy "src\launcher\core.py" "%RELEASE_DIR%\src\launcher\core.py" > nul
set "CFG=%RELEASE_DIR%\src\launcher\config.py"
> "%CFG%"  echo TEMPLATE_DIRNAME = "templates"
>>"%CFG%"  echo COREMODULE_NAME  = "core"
goto :CFG_DONE

:CFG_REB
echo     ...Configuring for [REB]...
:: REB 전용 src 모듈 추가 복사
echo     ...Adding 'reb' src module.
xcopy /E /I /Q "src\reb" "%RELEASE_DIR%\src\reb\"
:: REB 전용 launcher 파일 복사
xcopy /E /I /Q "src\launcher\templates_reb" "%RELEASE_DIR%\src\launcher\templates_reb\"
copy "src\launcher\core_reb.py" "%RELEASE_DIR%\src\launcher\core_reb.py" > nul
set "CFG=%RELEASE_DIR%\src\launcher\config.py"
> "%CFG%"  echo TEMPLATE_DIRNAME = "templates_reb"
>>"%CFG%"  echo COREMODULE_NAME  = "core_reb"
goto :CFG_DONE

:CFG_DONE

:: Add src path to the ._pth file for distribution
echo     ...Updating python ._pth file.
findstr /C:"..\src" "%RELEASE_DIR%\venv\python312._pth" > nul
if not %errorlevel% equ 0 (
    echo ..\src >> "%RELEASE_DIR%\venv\python312._pth"
)



echo [5/5] Creating archive: %OUTPUT_ZIP%
:: 압축할 폴더로 직접 이동
pushd "%RELEASE_DIR%"
:: 최상위 폴더에 있는 tools\7z.exe를 실행하여 압축
tar -a -c -f "%OUTPUT_ZIP%" . > nul
:: 원래 위치로 복귀
popd

echo.
echo ✅ Distribution packaging complete! (%FINAL_PROJECT_NAME%)



goto :eof



:: ==========================================
:: 빌드 및 복사를 수행하는 서브루틴
:: %1: 소스 파일명 (예: mainTRM)
:: %2: 결과 파일명 (예: Technical Reference Manual)
:: ==========================================
:BuildAndCopy
set "SRC_NAME=%~1"
set "DIST_NAME=%~2"

echo.
echo Building: %DIST_NAME%...

:: 1. 출력 디렉토리 생성 (이미 있으면 통과)
if not exist "dist\docs" mkdir "dist\docs"
if not exist "%RELEASE_DIR%\docs" mkdir "%RELEASE_DIR%\docs"

:: 2. LaTeX 빌드
pushd docs
%LATEX_COMPILER% -silent -pdf -outdir=../dist/docs "%SRC_NAME%.tex"
set "BUILD_ERROR=%errorlevel%"
popd

:: 3. 에러 체크
if %BUILD_ERROR% neq 0 (
    echo [ERROR] LaTeX build failed for %DIST_NAME%.
    pause
    exit /b %BUILD_ERROR%
)

:: 4. 배포 폴더로 복사 및 이름 변경
copy "dist\docs\%SRC_NAME%.pdf" "%RELEASE_DIR%\docs\%DIST_NAME%.pdf" > nul

echo     ...%DIST_NAME% build and copy successful.
exit /b 0