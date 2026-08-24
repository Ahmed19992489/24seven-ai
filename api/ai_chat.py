from http.server import BaseHTTPRequestHandler
import json
import os
import requests

# 🔑 API Keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def generate_limousine_reply(user_query, recent_context=""):
    q = user_query.lower().strip()
    
    # 1. Quick High-Quality Rule-Based Smart Replies for Egyptian Limousine Customers
    if any(w in q for w in ["سلام", "مرحبا", "مساء الخير", "صباح الخير", "اهلا", "أهلا", "ازيك", "ازيكم", "السلام عليكم"]):
        return "وعليكم السلام ورحمة الله وبركاته، أهلاً بحضرتك في 24Seven لخدمات الليموزين والنقل السياحي 🚗✨\nيسعدنا خدمتك، ممكن توضح لنا تفاصيل المشوار (مكان التحرك، الوصول، والموعد)؟"
    
    if any(w in q for w in ["اسعار", "أسعار", "كام", "بكام", "تكلفة", "سعر", "price", "cost"]):
        return "تحت أمرك يا فندم 🌹 لتحديد أفضل سعر متاح لرحلتك، يرجى تزويدنا بـ:\n📍 مكان التحرك\n📍 مكان الوصول\n📅 تاريخ وموعد الرحلة\n👥 عدد الأفراد ونوع السيارة المطلوبة."
    
    if any(w in q for w in ["مطار", "airport", "حجز", "عايز احجز", "حجز رحلة", "ممكن احجز", "احجز"]):
        return "أهلاً بك يا فندم ✈️ متاح لدينا أحدث السيارات لرحلات المطار والمحافظات 24 ساعة.\nمن فضلك أرسل تاريخ وموعد الرحلة ونقطة الانطلاق لتأكيد الحجز فوراً."
    
    if any(w in q for w in ["تسلم", "شكرا", "شكراً", "تمام", "تسلمي", "حبيبي", "الف شكر"]):
        return "العفو يا فندم، في خدمتكم دائماً ونتمنى لحضرتك يوم سعيد ورحلة موفقة بإذن الله 🌹✨"

    # 2. Try Groq AI if Key is set
    if GROQ_API_KEY:
        try:
            url = 'https://api.groq.com/openai/v1/chat/completions'
            headers = {
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            }
            system_prompt = (
                "أنت مساعد خدمة عملاء ذكي ومحترف لشركة ليموزين ونقل سياحي اسمها '24Seven Limousine' في مصر.\n"
                "اكتب رداً مهذباً بالعامية المصرية الراقية على استفسار العميل، واطلب تفاصيل المشوار (مكان التحرك، الوصول، والوقت).\n"
                "اجعل الرد مختصراً في سطرين فقط وبدون أي مقدمات أو شرح إضافي."
            )
            payload = {
                'model': 'llama-3.3-70b-versatile',
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f"سياق:\n{recent_context}\n\nرسالة العميل: {user_query}"}
                ],
                'max_tokens': 150,
                'temperature': 0.3
            }
            r = requests.post(url, headers=headers, json=payload, timeout=4)
            if r.status_code == 200:
                ai_text = r.json()['choices'][0]['message']['content'].strip()
                if ai_text:
                    return ai_text
        except Exception:
            pass

    # 3. Fallback
    return "أهلاً بحضرتك يا فندم 🌹 تفضل بتوضيح تفاصيل مشوارك (التحرك، الوصول، والتاريخ) وسنوافيك بالأسعار وتأكيد الحجز فوراً."

class handler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, ngrok-skip-browser-warning")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "service": "ai_chat"}).encode('utf-8'))

    def do_POST(self):
        try:
            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len).decode('utf-8')
            data = json.loads(post_body) if post_body else {}

            messages = data.get("messages", [])
            last_content = ""
            context = ""
            if messages:
                last_content = messages[-1].get("content", "")
                context = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in messages[:-1]])

            prompt = data.get("prompt") or last_content or "مرحبا"

            answer = generate_limousine_reply(prompt, context)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "answer": answer, "reply": answer}).encode('utf-8'))

        except Exception as e:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success", 
                "answer": "أهلاً بحضرتك يا فندم 🌹 تفضل بتوضيح تفاصيل مشوارك وسنوافيك بالأسعار فوراً.",
                "reply": "أهلاً بحضرتك يا فندم 🌹 تفضل بتوضيح تفاصيل مشوارك وسنوافيك بالأسعار فوراً."
            }).encode('utf-8'))
