#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import re
import requests
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# --- الإعدادات ---
TELEGRAM_TOKEN = "8347137740:AAH3OlqBXL7YOqfpHuCxk7Hv99SNu9Y6Nwo"
GEMINI_API_KEY = "AIzaSyBTYzZcXoQu5j5-REgcmeU1YbTCOIoT-ts"
FORMSPREE_URL = "https://formspree.io/f/xzddpdga"
ADMIN_ID = 5304804752

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_data = {}

def call_gemini_brute_force(prompt: str) -> str:
    """محاولة استدعاء الموديل بـ 3 طرق مختلفة لكسر عقدة الـ 404"""
    
    # قائمة الروابط المحتملة (المستقرة، البيتا، والموديل الأقدم)
    endpoints = [
        # 1. النسخة المستقرة - فلاش
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        # 2. النسخة المستقرة - برو (أقوى وأضمن)
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}",
        # 3. النسخة v1 (بدون بيتا)
        f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    ]
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    for url in endpoints:
        try:
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            if 'candidates' in result:
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                logger.error(f"Try failed for {url.split('/')[-1].split(':')[0]}: {result.get('error', {}).get('message')}")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            
    return "معاك يا فندم، سامعك.. كمل كلامك بخصوص تطوير سيستم الشركة وهرد عليك فوراً."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data[uid] = {'name': update.effective_user.first_name, 'phone': None}
    await update.message.reply_text("🚀 أهلاً بك في 24Seven AI! قولي إيه التحدي اللي بيواجهك؟")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    
    # تنبيه الأدمن
    if uid != ADMIN_ID:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔍 من {update.effective_user.first_name} ({uid}): {text}")

    # سحب الموبايل
    if re.search(r'(01[0125]\d{8})', text):
        user_data[uid] = {'phone': re.search(r'(01[0125]\d{8})', text).group(0)}
        kb = [[InlineKeyboardButton("✅ إرسال البيانات", callback_data='send')]]
        await update.message.reply_text("بياناتك وصلت! نبعتها لم. أحمد؟", reply_markup=InlineKeyboardMarkup(kb))
        return

    await update.message.chat.send_action(action="typing")
    reply = call_gemini_brute_force(f"رد كخبير مبيعات بشركة 24Seven AI بلهجة مصرية قصيرة: {text}")
    await update.message.reply_text(reply)

async def cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == 'send':
        requests.post(FORMSPREE_URL, data=user_data.get(q.from_user.id, {}))
        await q.edit_message_text("✅ تم الإرسال!")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 البوت يعمل بنظام البحث عن موديل متاح...")
    app.run_polling()

if __name__ == '__main__':
    main()