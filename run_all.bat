@echo off
chcp 65001 > nul
title 24Seven Local Runner
echo.
echo ===================================================
echo Starting 24Seven Local Services (WhatsApp, SQL Sync, Bots)...
echo Messenger is Running 24/7 on Vercel Cloud!
echo ===================================================
echo.

REM تنظيف أي عمليات سابقة معلقة على البورتات لمنع تعارض EADDRINUSE
taskkill /f /im node.exe 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3001') do taskkill /f /pid %%a 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000') do taskkill /f /pid %%a 2>nul

start "import_reservations" cmd /k "python -u import_reservations.py"
timeout /t 1 > nul

start "sync_to_neon" cmd /k "python -u sync_to_neon.py"
timeout /t 1 > nul

start "sync_full_data" cmd /k "python -u sync_full_data.py"
timeout /t 1 > nul

start "webhook_server" cmd /k "python -u webhook_server.py"
timeout /t 1 > nul

start "whatsapp_gateway" cmd /k "cd 24Seven_SaaS_Platform\whatsapp_gateway && node gateway.js"
timeout /t 1 > nul

start "automation_watcher" cmd /k "python -u automation_watcher.py"
timeout /t 1 > nul

start "run_sniper_bot" cmd /k "python -u run_sniper_bot.py"
timeout /t 1 > nul

start "limo_bot" cmd /k "cd c:\Users\pc2\LimoBot && python -u main.pyw"
timeout /t 1 > nul

echo.
echo ===================================================
echo [OK] All Local Services Running!
echo [Cloud Webhook] https://24seven-ai.com/api/messenger
echo ===================================================
