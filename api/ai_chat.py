from fastapi import FastAPI, Body, HTTPException
import requests
import os
from dotenv import load_dotenv

# تحميل متغيرات البيئة (يعمل محلياً وفي Vercel)
load_dotenv()

app = FastAPI()

# 🔑 Anthropic API Key
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

@app.post("/api/ai_chat")
async def ai_chat_handler(payload: dict = Body(...)):
    """
    نقطة اتصال ذكاء اصطناعي مخصصة لـ Vercel
    """
    if not ANTHROPIC_API_KEY:
        return {"answer": "❌ خطأ: لم يتم ضبط مفتاح ANTHROPIC_API_KEY في إعدادات السيرفر."}

    system_prompt = payload.get("system", "أنت مساعد ذكي لشركة ليموزين.")
    messages = payload.get("messages", [])
    max_tokens = payload.get("max_tokens", 1000)

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    data = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": messages
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            return {"answer": f"❌ خطأ من Claude API: {response.text}"}
        
        resp_json = response.json()
        answer = resp_json['content'][0]['text']
        return {"answer": answer}
    
    except Exception as e:
        return {"answer": f"❌ خطأ في الاتصال: {str(e)}"}

# تأكيد التشغيل كدالة Vercel
handler = app
