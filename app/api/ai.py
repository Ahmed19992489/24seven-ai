from fastapi import APIRouter, Body, HTTPException
import requests
import json
import os

router = APIRouter()

@router.post("/ai_chat")
async def ai_chat_endpoint(payload: dict = Body(...)):
    """
    بروكسي للاتصال بـ Gemini API من Google لضمان أمن المفتاح وسهولة الاستخدام
    """
    system_prompt = payload.get("system", "أنت مساعد ذكي لشركة ليموزين.")
    messages = payload.get("messages", [])
    max_tokens = payload.get("max_tokens", 1000)

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"

    contents = []
    for msg in messages:
        role = msg.get("role")
        if role == "assistant":
            role = "model"
        elif role != "model":
            role = "user"
        contents.append({
            "role": role,
            "parts": [{"text": msg.get("content", "")}]
        })

    gemini_payload = {
        "contents": contents
    }
    if system_prompt:
        gemini_payload["systemInstruction"] = {
            "parts": [{"text": system_prompt}]
        }
    gemini_payload["generationConfig"] = {
        "maxOutputTokens": max_tokens,
        "temperature": 0.2
    }

    try:
        response = requests.post(url, json=gemini_payload, headers={"Content-Type": "application/json"})
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Gemini API Error: {response.text}")
        
        resp_json = response.json()
        answer = resp_json['candidates'][0]['content']['parts'][0]['text']
        return {"answer": answer}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

