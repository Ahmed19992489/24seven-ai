import json
import os
import urllib.request
import urllib.error

def handler(request):
    """
    نسخة مبسطة جداً لضمان العمل على Vercel بدون مشاكل مكتبات
    """
    # 🔑 Gemini API Key
    api_key = os.environ.get("GEMINI_API_KEY", "")

    if request.method != "POST":
        return {
            "statusCode": 405,
            "body": json.dumps({"answer": "Only POST allowed"})
        }

    try:
        # قراءة البيانات من الطلب
        body_unicode = request.body.decode('utf-8')
        payload = json.loads(body_unicode)
        
        system_prompt = payload.get("system", "أنت مساعد ذكي لشركة ليموزين.")
        messages = payload.get("messages", [])
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        
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
            "maxOutputTokens": 1000,
            "temperature": 0.2
        }

        data = json.dumps(gemini_payload).encode('utf-8')
        headers = {
            "content-type": "application/json"
        }

        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        
        with urllib.request.urlopen(req) as response:
            resp_data = response.read().decode('utf-8')
            resp_json = json.loads(resp_data)
            answer = resp_json['candidates'][0]['content']['parts'][0]['text']
            
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"answer": answer})
            }

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8')
        return {
            "statusCode": 200,
            "body": json.dumps({"answer": f"❌ خطأ من Gemini: {err_msg}"})
        }
    except Exception as e:
        return {
            "statusCode": 200,
            "body": json.dumps({"answer": f"❌ خطأ داخلي: {str(e)}"})
        }

