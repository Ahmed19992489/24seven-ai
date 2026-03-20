from fastapi import APIRouter, Body, HTTPException
import requests
import json
import os

router = APIRouter()

# 🔑 Anthropic API Key (يتم جلبه من متغيرات البيئة للأمان)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

@router.post("/ai_chat")
async def ai_chat_endpoint(payload: dict = Body(...)):
    """
    بروكسي للاتصال بـ Claude API من Anthropic لضمان أمن المفتاح وسهولة الاستخدام
    """
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
            raise HTTPException(status_code=response.status_code, detail=f"Claude API Error: {response.text}")
        
        resp_json = response.json()
        answer = resp_json['content'][0]['text']
        return {"answer": answer}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
