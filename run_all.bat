@echo off
title 24Seven Master Runner
cd /d "%~dp0"
if exist "24Seven_SaaS_Platform" (
    cd /d "%~dp024Seven_SaaS_Platform"
)

cls
echo ===================================================
echo   24Seven Limousine - Running Local Services
echo   Database: Neon PostgreSQL
echo   Cloud Webhook: https://24seven-ai.com
echo ===================================================
echo.

REM Clean hanging Node.js and Python processes
taskkill /f /im node.exe 2>nul
taskkill /f /im python.exe 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3001 2^>nul') do taskkill /f /pid %%a 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 2^>nul') do taskkill /f /pid %%a 2>nul

echo [1/6] Starting import_reservations...
start "import_reservations" cmd /k python -u import_reservations.py
ping -n 2 127.0.0.1 >nul

echo [2/6] Starting sync_to_neon...
start "sync_to_neon" cmd /k python -u sync_to_neon.py
ping -n 2 127.0.0.1 >nul

echo [3/6] Starting webhook_server...
start "webhook_server" cmd /k python -u webhook_server.py
ping -n 2 127.0.0.1 >nul

echo [4/6] Starting whatsapp_gateway...
if exist "whatsapp_gateway\gateway.js" (
    start "whatsapp_gateway" /d "%cd%\whatsapp_gateway" cmd /k node gateway.js
) else if exist "..\whatsapp_gateway\gateway.js" (
    start "whatsapp_gateway" /d "%cd%\..\whatsapp_gateway" cmd /k node gateway.js
)
ping -n 2 127.0.0.1 >nul

echo [5/6] Starting automation_watcher...
start "automation_watcher" cmd /k python -u automation_watcher.py
ping -n 2 127.0.0.1 >nul

echo [6/6] Starting run_sniper_bot...
start "run_sniper_bot" cmd /k python -u run_sniper_bot.py
ping -n 2 127.0.0.1 >nul

if exist "c:\Users\pc2\LimoBot\main.py" (
    start "limo_bot" /d "c:\Users\pc2\LimoBot" cmd /k python -u main.py
)

echo.
echo ===================================================
echo   [OK] All Local Services Started Successfully!
echo ===================================================
echo.
pause
