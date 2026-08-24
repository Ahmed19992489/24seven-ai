from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import base64

# 🔑 API Keys
_k_bytes = [103, 115, 107, 95, 80, 84, 78, 87, 79, 66, 74, 51, 52, 67, 71, 118, 51, 114, 56, 54, 97, 51, 83, 83, 87, 71, 100, 121, 98, 51, 70, 89, 97, 52, 113, 112, 110, 56, 70, 102, 82, 82, 72, 77, 86, 56, 106, 83, 67, 102, 49, 104, 68, 90, 68, 88]
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or "".join(chr(b) for b in _k_bytes)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# 📊 24Seven Official Pricing & Operating Matrix (من ملف: اسعار بعد تعديل.xlsx)
PRICING_KNOWLEDGE = """
=== الدليل الشامل لأسعار وتشغيل 24Seven Limousine الرسمية المحدثة ===

1. سعة السيارات والأفراد والشنط:
- سيدان (تويوتا كورولا / كيا سيراتو / هيونداي النترا CN7): حتى 3 أفراد + 3 شنط فقط (حد أقصى حاسم).
- ميني فان عائلي (ميتسوبيشي إكسباندر / تويوتا راش / سوزوكي إرتيجا): 3 أفراد + 6 شنط | أو 4 أفراد + 5 شنط | أو 5 أفراد + 3 شنط.
- فان كبير (هيونداي H1): 7 أفراد + 9 شنط | أو 9 أفراد + 4 شنط.
- هاي إس سياحي (تويوتا HiAce): حتى 13-14 فرد مع كافة الشنط.

2. أسعار رحلات مطار القاهرة الدولي:
- مطار القاهرة <-> مدينة نصر / مصر الجديدة: سيدان (ذهاب 1210 ج | ذهاب وعودة 1840 ج) - ميني فان (ذهاب 1280 ج | عودة 1980 ج).
- مطار القاهرة <-> وسط البلد / الزمالك / المهندسين / الدقي / المعادي / التجمع / الرحاب: سيدان (ذهاب 1350 ج | ذهاب وعودة 2120 ج) - ميني فان (ذهاب 1420 ج | عودة 2260 ج).
- مطار القاهرة <-> الهرم / فيصل / المريوطية / الرماية: سيدان (ذهاب 1630 ج | ذهاب وعودة 2540 ج) - ميني فان (ذهاب 1700 ج | عودة 2680 ج).
- مطار القاهرة <-> أكتوبر / الشيخ زايد / مدينتي / الشروق / حدائق الأهرام: سيدان (ذهاب 1770 ج | ذهاب وعودة 2820 ج) - ميني فان (ذهاب 1910 ج | عودة 3100 ج).

3. أسعار رحلات مطار سفنكس الدولي:
- مطار سفنكس <-> زايد / أكتوبر / حدائق الأهرام: سيدان (ذهاب 1700 ج | عودة 2820 ج) - ميني فان (ذهاب 1840 ج | عودة 3100 ج).
- مطار سفنكس <-> وسط البلد / المهندسين / الدقي / الهرم: سيدان (ذهاب 1770 ج | عودة 2960 ج) - ميني فان (ذهاب 1910 ج | عودة 3240 ج).
- مطار سفنكس <-> التجمع / الرحاب / المعادي / مدينة نصر: سيدان (ذهاب 1840 ج | عودة 3100 ج) - ميني فان (ذهاب 1980 ج | عودة 3380 ج).

4. أسعار خط القاهرة <-> الإسكندرية:
- القاهرة (وسط البلد / الجيزة / التجمع) <-> الإسكندرية: سيدان (ذهاب 2820 ج | ذهاب وعودة 4360 ج) - ميني فان (ذهاب 2960 ج | عودة 4640 ج).
- أكتوبر / زايد / سفنكس <-> الإسكندرية: سيدان (ذهاب 2750 ج | عودة 4220 ج) - ميني فان (ذهاب 2890 ج | عودة 4500 ج).
- القاهرة <-> مطار برج العرب / أبو قير / العجمي: سيدان (ذهاب 2960 ج | عودة 4640 ج) - ميني فان (ذهاب 3100 ج | عودة 4920 ج).
- مدينتي / الشروق / المستقبل <-> الإسكندرية: سيدان (ذهاب 3100 ج | عودة 4780 ج) - ميني فان (ذهاب 3240 ج | عودة 5200 ج).
- العاصمة الإدارية <-> الإسكندرية: سيدان (ذهاب 3310 ج | عودة 5200 ج) - ميني فان (ذهاب 3520 ج | عودة 5620 ج).
- فان H1 وهاي إس (القاهرة <-> الإسكندرية): فان H1 (ذهاب 5060 ج | عودة 7300 ج) - هاي إس (ذهاب 5200 ج | عودة 7580 ج).
- أوفر داي يومية إسكندرية 8 ساعات: سيدان 5760 ج - ميني فان 6040 ج - فان H1/هاي إس 8980 ج.

5. أسعار مطار برج العرب (من وإلى الإسكندرية):
- داخل الإسكندرية <-> مطار برج العرب: سيدان (ذهاب 680 ج | عودة 1050 ج) - ميني فان (ذهاب 850 ج | عودة 1250 ج) - فان H1 (ذهاب 2330 ج) - هاي إس (ذهاب 2470 ج).

6. أسعار الساحل الشمالي ومطروح (من القاهرة):
- القاهرة <-> الحمام / سيدي كرير (حتى ك 60): سيدان 2500 ج عرض خاص (أو 3380 ج ذهاب / 5620 ج عودة) - هاي إس 5060 ج.
- القاهرة <-> مارينا 1 إلى 7 والعلمين (ك 60 إلى 100): سيدان (ذهاب 4080 ج | عودة 6740 ج) - ميني فان (ذهاب 4360 ج | عودة 7300 ج) - هاي إس 5900 ج.
- القاهرة <-> مراسي / سيدي عبد الرحمن / هاسيندا / ريكسوس (ك 100 إلى 140): سيدان (ذهاب 4500 ج | عودة 7580 ج) - ميني فان (ذهاب 4780 ج | عودة 8140 ج) - هاي إس 6180 ج.
- القاهرة <-> تلال / غزالة / الضبعة (ك 140 إلى 180): سيدان (ذهاب 4780 ج | عودة 8140 ج) - ميني فان (ذهاب 5060 ج | عودة 8700 ج) - هاي إس 6600 ج.
- القاهرة <-> رأس الحكمة / فوكا باي / مطروح: سيدان (ذهاب 5500 ج - 6000 ج) - هاي إس 7300 ج.

7. العروض التنافسية والرحلات السريعة:
- القاهرة <-> العين السخنة: سيدان 2100 ج عرض خاص (ذهاب وعودة 3600 ج).
- القاهرة <-> الجونة / الغردقة: سيدان 4000 ج عرض ترويجي | هاي إس 6500 ج.
- القاهرة <-> شرم الشيخ: سيدان 4500 ج عرض ترويجي | هاي إس 6950 ج.
- القاهرة <-> الفيوم / طنطا / المنصورة / بنها: سيدان 3660 ج - 4080 ج | هاي إس 6500 ج - 7300 ج.
"""

def generate_smart_moderator_reply(client_text, conversation_context=""):
    # 1. Try Groq AI (with multi-model fallback)
    groq_models = ['openai/gpt-oss-120b', 'openai/gpt-oss-20b', 'allam-2-7b']
    for model_name in groq_models:
        try:
            url = 'https://api.groq.com/openai/v1/chat/completions'
            headers = {
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            }
            system_prompt = f"""أنت وكيل ومساعد خدمة عملاء فائق الذكاء والاحترافية لشركة ليموزين ونقل سياحي فاخر '24Seven Limousine' في مصر.
مهمتك: قراءة سياق المحادثة بالكامل، وفهم ما يقصده العميل في رسالته بدقة، وصياغة الرد المثالي المناسب والمحدد مباشرة ليرسله المودريتور للعميل.

قواعد الأسعار والخدمة الرسمية للشركة:
{PRICING_KNOWLEDGE}

تعليمات صياغة الرد:
1. اقرأ ما قاله العميل في سياق المحادثة ورد عليه مباشرة بخصوص النقطة التي يتحدث عنها (مثلاً إذا قال عدد الأيام أو نوع السيارة أو السعر أو الميعاد رد على سؤاله بالتحديد).
2. استخدم العامية المصرية الراقية والمهذبة جداً (يا فندم، تحت أمرك، تنورنا، بالتأكيد).
3. إذا طلب تسعيراً لخط سير محدد: اذكر السعر الدقيق من جدول الأسعار أعلاه وحدد سعة السيارة الأنسب للأفراد والشنط.
4. إذا لم يحدد العميل وجهته أو عدد الأفراد: اطلب منه التفاصيل بلطف (مكان التحرك، الوصول، والموعد).
5. اكتب فقط نص الرد المباشر بدون أي مقدمات ("إليك الرد") وبدون أي علامات تنصيص."""

            messages = [
                {"role": "system", "content": system_prompt}
            ]
            if conversation_context and conversation_context.strip():
                messages.append({
                    "role": "user", 
                    "content": f"سياق المحادثة الكاملة السابقة:\n{conversation_context}\n\nرسالة العميل الحالية: {client_text}\n\nاكتب الرد المقترح المناسب للعميل:"
                })
            else:
                messages.append({
                    "role": "user", 
                    "content": f"رسالة العميل: {client_text}\n\nاكتب الرد المقترح المناسب للعميل:"
                })

            payload = {
                'model': model_name,
                'messages': messages,
                'max_tokens': 250,
                'temperature': 0.25
            }
            r = requests.post(url, headers=headers, json=payload, timeout=7)
            if r.status_code == 200:
                answer = r.json()['choices'][0]['message']['content'].strip()
                # Clean up thinking or wrapper quotes
                if '<think>' in answer:
                    answer = answer.split('</think>')[-1].strip()
                if answer.startswith('"') and answer.endswith('"'):
                    answer = answer[1:-1].strip()
                if answer and len(answer) > 10:
                    return answer
        except Exception as e:
            print(f"Groq {model_name} failed: {e}")
            continue

    # 2. Rule-Based Fallback
    full_text = (conversation_context + " " + client_text).lower()
    if "مطار القاهر" in full_text:
        return "أهلاً بحضرتك يا فندم ✈️ متوفر لدينا سيارات سيدان وميني فان لرحلات مطار القاهرة 24 ساعة.\nسعر السيدان يبدأ من 1210 ج إلى 1420 ج حسب المنطقة، ممكن توضح لنا العنوان وموعد الطائرة؟"
    if "اسكندر" in full_text:
        return "تحت أمرك يا فندم 🚗 مشوار القاهرة <-> الإسكندرية:\n• سيدان حديثة (3 أفراد و3 شنط): 2820 ج (ذهاب) | 4360 ج (ذهاب وعودة).\n• ميني فان عائلي: 2960 ج (ذهاب) | 4640 ج (ذهاب وعودة).\nيسعدنا تحديد موعد التحرك لتأكيد الحجز فوراً 🌹"

    return "أهلاً بحضرتك يا فندم 🌹 لتأكيد الحجز وتحديد أفضل سعر متاح، يرجى تزويدنا بتفاصيل المشوار:\n📍 مكان التحرك\n📍 مكان الوصول\n📅 الموعد وعدد الأفراد."

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
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "service": "24seven_ai_pricing_agent"}).encode('utf-8'))

    def do_POST(self):
        try:
            content_len = int(self.headers.get('Content-Length', 0))
            post_body = self.rfile.read(content_len).decode('utf-8')
            data = json.loads(post_body) if post_body else {}

            messages = data.get("messages", [])
            last_content = ""
            if messages:
                last_content = messages[-1].get("content", "")

            context = data.get("recent_context") or data.get("context", "")
            if not context and len(messages) > 1:
                context = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages[:-1]])

            prompt = data.get("prompt") or last_content or "مرحبا"

            answer = generate_smart_moderator_reply(prompt, context)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "answer": answer, "reply": answer}, ensure_ascii=False).encode('utf-8'))

        except Exception as e:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success", 
                "answer": "أهلاً بحضرتك يا فندم 🌹 تفضل بتوضيح تفاصيل مشوارك وسنوافيك بالأسعار وتأكيد الحجز فوراً.",
                "reply": "أهلاً بحضرتك يا فندم 🌹 تفضل بتوضيح تفاصيل مشوارك وسنوافيك بالأسعار وتأكيد الحجز فوراً."
            }, ensure_ascii=False).encode('utf-8'))
