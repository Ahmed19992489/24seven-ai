@echo off
chcp 65001 > nul
title 24Seven Local Master Runner
cd /d "%~dp0"
echo.
echo ===================================================
echo   🚗 24Seven Limousine - تشغيل كافة الخدمات المحلية
echo   ⚡ Database: Neon PostgreSQL
echo   🌐 Webhook: https://24seven-ai.com
echo ===================================================
echo.

REM تنظيف أي عمليات سابقة معلقة على البورتات لمنع تعارض EADDRINUSE
taskkill /f /im node.exe 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3001') do taskkill /f /pid %%a 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000') do taskkill /f /pid %%a 2>nul

echo [1/6] تشغيل مستورد الحجوزات (SQL Server / Google Sheet)...
start "import_reservations" cmd /k "python -u import_reservations.py"
timeout /t 1 > nul

echo [2/6] تشغيل مزامنة قاعدة البيانات (Google Sheet -> Neon DB)...
start "sync_to_neon" cmd /k "python -u sync_to_neon.py"
timeout /t 1 > nul

echo [3/6] تشغيل خادم الويب هوك المحلي (Webhook Server)...
start "webhook_server" cmd /k "python -u webhook_server.py"
timeout /t 1 > nul

echo [4/6] تشغيل بوابة الواتساب الرسمية (WhatsApp Baileys Gateway)...
if exist "whatsapp_gateway\gateway.js" (
    start "whatsapp_gateway" cmd /k "cd /d "%~dp0whatsapp_gateway" && node gateway.js"
) else if exist "24Seven_SaaS_Platform\whatsapp_gateway\gateway.js" (
    start "whatsapp_gateway" cmd /k "cd /d "%~dp024Seven_SaaS_Platform\whatsapp_gateway" && node gateway.js"
)
timeout /t 1 > nul

echo [5/6] تشغيل مراقب الأتمتة والعمليات (Automation Watcher)...
start "automation_watcher" cmd /k "python -u automation_watcher.py"
timeout /t 1 > nul

echo [6/6] تشغيل بوت القناص لتيليجرام (Telegram Sniper Bot)...
start "run_sniper_bot" cmd /k "python -u run_sniper_bot.py"
timeout /t 1 > nul

REM تشغيل بوت المساعد الشخصي إذا كان موجوداً
if exist "c:\Users\pc2\LimoBot\main.py" (
    start "limo_bot" cmd /k "cd /d c:\Users\pc2\LimoBot && python -u main.py"
)

echo.
echo ===================================================
echo   ✅ تم تشغيل جميع الخدمات المحلية بنجاح!
echo   🌐 السيرفر السحابي: https://24seven-ai.com
echo ===================================================
echo.
pause
