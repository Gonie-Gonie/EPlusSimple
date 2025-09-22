@echo off

echo ==============================
echo [1/4] Changing to working directory...
cd /d %~dp0/launcher/

echo [2/4] Waiting for the server to start... (about 3 seconds)
ping 127.0.0.1 -n 3 > nul

echo [3/4] Launching the web browser: http://127.0.0.1:5000
start "" "http://127.0.0.1:5000"

echo [4/4] Starting Flask server...
echo The server is now running. To stop it, close this window or press Ctrl+C.
echo ==============================

:: 'start' 명령어 없이 직접 실행하여 배치파일이 서버 프로세스를 제어하도록 함
"..\venv\python.exe" ".\server.py" --mode run


:: --- [추가된 부분] ---
:: 스크립트가 정상/비정상 종료된 후 사용자가 키를 누를 때까지 대기
echo.
echo ==============================
echo The server process has ended.
echo If it was unexpected, check for error messages above.




