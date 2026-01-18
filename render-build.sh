#!/usr/bin/env bash
# exit on error
set -o errexit

STORAGE_DIR=/opt/render/project/.render

echo "Cleaning up old cache..."
rm -rf $STORAGE_DIR/chrome

mkdir -p $STORAGE_DIR/chrome
cd $STORAGE_DIR/chrome

# 1. تحميل نسخة كروم مستقرة (Chrome for Testing - Stable)
echo "...Downloading Chrome (Stable 121)..."
wget -q https://storage.googleapis.com/chrome-for-testing-public/121.0.6167.85/linux64/chrome-linux64.zip
unzip -q chrome-linux64.zip
rm chrome-linux64.zip

# 2. تحميل الدرايفر المطابق لنفس النسخة تماماً
echo "...Downloading ChromeDriver (Stable 121)..."
wget -q https://storage.googleapis.com/chrome-for-testing-public/121.0.6167.85/linux64/chromedriver-linux64.zip
unzip -q chromedriver-linux64.zip
rm chromedriver-linux64.zip

# العودة للمجلد الرئيسي وتثبيت المكتبات
cd $HOME/project/src
pip install -r requirements.txt

# إعطاء صلاحيات التشغيل
chmod +x $STORAGE_DIR/chrome/chrome-linux64/chrome
chmod +x $STORAGE_DIR/chrome/chromedriver-linux64/chromedriver

echo "Build Completed Successfully!"