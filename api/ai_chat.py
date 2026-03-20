import json
import os
import urllib.request
import urllib.error

def handler(request):
    """
    نسخة مبسطة جداً لضمان العمل على Vercel بدون مشاكل مكتبات
    """
    # 🔑 Anthropic API Key
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if request.method != "POST":
        return {
            "statusCode": 405,
            "body": json.dumps({"answer": "Only POST allowed"})
        }

    if not api_key:
        return {
            "statusCode": 200,
            "body": json.dumps({"answer": "❌ خطأ المبرمج: لم يتم ضبط ANTHROPIC_API_KEY على Vercel."})
        }

    try:
        # قراءة البيانات من الطلب
        body_unicode = request.body.decode('utf-8')
        payload = json.loads(body_unicode)
        
        system_prompt = payload.get("system", "أنت مساعد ذكي لشركة ليموزين.")
        messages = payload.get("messages", [])
        
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        data = json.dumps({
            "model": "claude-3-haiku-20240307",
            "max_tokens": 1000,
            "system": system_prompt,
            "messages": messages
        }).encode('utf-8')

        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        
        with urllib.request.urlopen(req) as response:
            resp_data = response.read().decode('utf-8')
            resp_json = json.loads(resp_data)
            answer = resp_json['content'][0]['text']
            
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"answer": answer})
            }

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8')
        return {
            "statusCode": 200,
            "body": json.dumps({"answer": f"❌ خطأ من Claude: {err_msg}"})
        }
    except Exception as e:
        return {
            "statusCode": 200,
            "body": json.dumps({"answer": f"❌ خطأ داخلي: {str(e)}"})
        }
