import requests
import json
import os
import time
import threading
import re
from datetime import datetime, timedelta

# ==========================================
# 🔑 إعدادات قاعدة البيانات سوبابيز
# ==========================================
SUPABASE_URL = 'https://wtjwzqvmwnbvjxnmweqq.supabase.co'
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTQ2NTQwMywiZXhwIjoyMDg3MDQxNDAzfQ.WYNflQntWBCHXDnxFf2C1X1IerYZtMfMT6p6P4Dx0Vg")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ==========================================
# 🤖 إعدادات Groq / AI Parser
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are an expert data parsing assistant for a limousine and car booking platform in Egypt.
Your task is to parse a text message sent inside a WhatsApp group of limousine offices.
You must classify if the message is related to offering a trip for sale, requesting a car/driver, or exchanging a trip.
If it is NOT related to a trip (e.g. general greetings, ads, unrelated text), return:
{"is_trip_related": false}

If it is trip-related, return:
{
  "is_trip_related": true,
  "operation_type": "sale" or "request" or "exchange",
  "origin": "Cairo" or "Alexandria" or "Sahel" or "Sharm El Sheikh" or "Hurghada" or "Dahab" or "Taba" or "Marsa Matrouh" or other English name of city/airport,
  "destination": "Cairo" or "Alexandria" or "Sahel" or "Sharm El Sheikh" or "Hurghada" or "Dahab" or "Taba" or "Marsa Matrouh" or other English name of city/airport,
  "date_time": "Arabic/English description of date and time, e.g. 'غدا الساعة 11 ص'",
  "price": number or null,
  "car_type": "sedan" (for Corolla/Cerato/Elantra) or "minivan" (for Xpander/Rush/Eagle/Glory/Ertiga/Tiggo 8) or "van" (for HiAce) or "coaster" or null,
  "client_type": "أجانب" or "عائلات" or null,
  "contact_phone": "Clean international phone number without +, e.g., 201559223305",
  "office_name": "Name of limousine office if mentioned"
}

Guidance for classification:
- 'sale' (بيع): Sender has a booking and wants to sell it (e.g., 'لو تلزم زميل', 'معايا رحلة', 'عندي عودة من مارينا', 'هاي اس شكل جديد للبيع').
- 'request' (طلب): Sender is looking for a car/driver (e.g., 'مطلوب كورولا', 'مين يخلص', 'توصيلة من القاهرة').
- 'exchange' (بدل): Sender wants to swap trips (e.g., 'بدل').

Guidance for car_type:
- 'sedan' (سيدان): Corolla (كورولا), Cerato (سيراتو), Elantra (النترا / إلنترا), basic sedan cars.
- 'minivan' (ليموزين / ميني فان / SUV): Xpander (اكسبندر / إكسابندر), Rush (راش), Eagle (إيجل), Glory (جلورى / جلوري), Ertiga (أورتيجا / ارتيجا), Tiggo 8 (تيجو 8 / تيجو).
- 'van' (فان): Toyota HiAce (هاي اس / تويوتا هاي اس).
- 'coaster' (كوستر).

Extract the contact phone number from the text if a number is mentioned (like 'للتواصل / 01559223305' or any number starting with 01...). Format it to start with '20' (e.g., '201559223305'). If no phone number is mentioned in the text, leave it null.

Return ONLY valid JSON. No comments, no markdown wrapping, no formatting other than JSON."""

# ==========================================
# 🛠️ دوال مساعدة للإعدادات
# ==========================================
def get_setting(key):
    try:
        url = f"{SUPABASE_URL}/rest/v1/sniper_settings?key=eq.{key}&select=value"
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code == 200 and r.json():
            return r.json()[0].get("value")
    except Exception as e:
        print(f"[Sniper Setting] Error getting {key}: {e}")
    return None

def save_setting(key, value):
    try:
        url = f"{SUPABASE_URL}/rest/v1/sniper_settings?on_conflict=key"
        payload = {"key": key, "value": value}
        r = requests.post(url, headers=HEADERS, json=payload, timeout=5)
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"[Sniper Setting] Error saving {key}: {e}")
        return False

# ==========================================
# 🤖 استدعاء الذكاء الاصطناعي
# ==========================================
def call_ai_parser(text):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this WhatsApp message:\n\n{text}"}
        ],
        "temperature": 0.0,
        "max_tokens": 500
    }
    try:
        r = requests.post(GROQ_URL, json=payload, headers=headers, timeout=20)
        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content'].strip()
            # تنظيف المحتوى من أي كتل كودية ماركداون
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return json.loads(content.strip())
        else:
            print(f"[Sniper AI ERROR] Status {r.status_code}: {r.text}")
    except Exception as e:
        print(f"[Sniper AI Exception]: {e}")
    return None

# ==========================================
# 🔄 محرك المطابقة ومنع التكرار
# ==========================================
def normalize_city_name(city):
    if not city: return ""
    c = city.lower().strip()
    if 'cairo' in c or 'قاهرة' in c or 'قاهره' in c: return 'cairo'
    if 'alex' in c or 'إسكندرية' in c or 'اسكندرية' in c or 'اسكندريه' in c: return 'alexandria'
    if 'sahel' in c or 'ساحل' in c: return 'sahel'
    if 'sharm' in c or 'شرم' in c: return 'sharm_el_sheikh'
    if 'hurghada' in c or 'غردقة' in c or 'غردقه' in c: return 'hurghada'
    if 'dahab' in c or 'دهب' in c: return 'dahab'
    if 'taba' in c or 'طابا' in c: return 'taba'
    if 'matrouh' in c or 'مطروح' in c: return 'marsa_matrouh'
    return c

def is_duplicate(origin, destination, date_time, contact_phone):
    try:
        # البحث في الرحلات التي دخلت في آخر 15 دقيقة
        time_limit = (datetime.utcnow() - timedelta(minutes=15)).isoformat() + "Z"
        url = f"{SUPABASE_URL}/rest/v1/sniper_parsed_trips"
        params = {
            "origin": f"eq.{origin}",
            "destination": f"eq.{destination}",
            "contact_phone": f"eq.{contact_phone}",
            "created_at": f"gte.{time_limit}",
            "select": "id"
        }
        r = requests.get(url, headers=HEADERS, params=params, timeout=5)
        if r.status_code == 200 and r.json():
            return True
    except Exception as e:
        print(f"[Sniper Dedup Error]: {e}")
    return False

def check_match(trip_data):
    try:
        url = f"{SUPABASE_URL}/rest/v1/sniper_filters?select=*"
        r = requests.get(url, headers=HEADERS, timeout=5)
        if r.status_code != 200:
            return False
        filters = r.json()
    except Exception as e:
        print(f"[Sniper Match Error]: {e}")
        return False

    # ✅ لو مفيش فلاتر → ابعت كل رسائل البيع والبدل تلقائياً
    if not filters:
        op = trip_data.get("operation_type", "")
        if op in ("sale", "exchange"):
            return True
        return False

    trip_origin = normalize_city_name(trip_data.get("origin"))
    trip_dest = normalize_city_name(trip_data.get("destination"))
    trip_car = trip_data.get("car_type") # sedan, minivan, van

    for f in filters:
        f_origin = normalize_city_name(f.get("origin"))
        f_dest = normalize_city_name(f.get("destination"))
        f_car = f.get("car_type") # sedan, minivan, van or null/empty

        if trip_origin == f_origin and trip_dest == f_dest:
            if not f_car or f_car.lower().strip() == 'any' or f_car.lower().strip() == trip_car:
                return True
    return False


# ==========================================
# 📣 إشعارات التلجرام والواتساب
# ==========================================
def send_telegram_alert(message_text):
    token = get_setting("telegram_token")
    chat_id = get_setting("telegram_chat_id")
    if not token or not chat_id:
        print(f"[Telegram Alert] Skipped. Token: {bool(token)}, Chat ID: {bool(chat_id)}")
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[Telegram Alert Exception]: {e}")
        return False

def format_telegram_alert(trip):
    op_type_map = {"sale": "🟢 بيع (لو تلزم زميل)", "request": "🔵 طلب تشغيلة", "exchange": "🟡 بدل"}
    op_type = op_type_map.get(trip.get("operation_type"), trip.get("operation_type", ""))
    
    car_type_map = {"sedan": "سيدان (كورولا/سيراتو/إلنترا)", "minivan": "ميني فان (إكسابندر/راش/تيجو)", "van": "فان (تويوتا هاي إس)", "coaster": "كوستر"}
    car_type = car_type_map.get(trip.get("car_type"), trip.get("car_type") or "غير محدد")
    
    price = f"{trip.get('price')} جنيهاً" if trip.get('price') else "غير محدد"
    office = trip.get('office_name') or "غير مذكور"
    client = trip.get('client_type') or "طبيعي"
    phone = trip.get('contact_phone')
    
    msg = f"🎯 <b>تنبيه تشغيلة مطابقة لقناص 24Seven!</b>\n\n"
    msg += f"<b>نوع العملية:</b> {op_type}\n"
    msg += f"<b>خط السير:</b> من <b>{trip.get('origin')}</b> إلى <b>{trip.get('destination')}</b>\n"
    msg += f"<b>التاريخ/الوقت:</b> {trip.get('date_time')}\n"
    msg += f"<b>السيارة المطلوبة:</b> {car_type}\n"
    msg += f"<b>السعر المعروض:</b> {price}\n"
    msg += f"<b>نوع العميل:</b> {client}\n"
    msg += f"<b>اسم المكتب:</b> {office}\n"
    msg += f"<b>الجروب:</b> {trip.get('group_name')}\n"
    msg += f"<b>الناشر:</b> {trip.get('sender_name')}\n\n"
    msg += f"📞 <b>رقم التواصل:</b> <code>{phone}</code>\n"
    msg += f"💬 <a href='https://wa.me/{phone}'><b>اضغط هنا لمراسلة صاحب الرحلة فوراً على واتساب</b></a>"
    return msg

# ==========================================
# 🔄 حلقة الاستماع لتسجيل التلجرام تلقائياً (Polling)
# ==========================================
def start_telegram_polling():
    def poll():
        print("[Telegram Bot] Starting long polling thread...")
        last_update_id = 0
        token = None
        
        while True:
            if not token:
                token = get_setting("telegram_token")
                if not token:
                    time.sleep(10)
                    continue
                
            url = f"https://api.telegram.org/bot{token}/getUpdates"
            try:
                params = {"offset": last_update_id + 1, "timeout": 20}
                r = requests.get(url, params=params, timeout=25)
                if r.status_code == 200:
                    resp = r.json()
                    if resp.get("ok") and resp.get("result"):
                        for update in resp["result"]:
                            update_id = update["update_id"]
                            last_update_id = max(last_update_id, update_id)
                            
                            message = update.get("message")
                            if message:
                                chat_id = message["chat"]["id"]
                                text = message.get("text", "").strip()
                                
                                if text == "/start":
                                    save_setting("telegram_chat_id", str(chat_id))
                                    welcome_text = "<b>مرحباً بك في نظام قناص التشغيلات لـ 24Seven!</b>\n\nتم ربط حساب التلجرام الخاص بك بنجاح. ستصلك الإشعارات الفورية هنا فور مطابقة أي تشغيلة للفلاتر الحالية."
                                    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                        "chat_id": chat_id,
                                        "text": welcome_text,
                                        "parse_mode": "HTML"
                                    })
                                    print(f"[Telegram Bot] Successfully registered chat_id: {chat_id}")
            except Exception as e:
                # print(f"[Telegram Bot Polling Error]: {e}")
                pass
            time.sleep(5)
            
    t = threading.Thread(target=poll, daemon=True)
    t.start()

# ==========================================
# ⚡ معالجة الرسالة القادمة من المجموعات
# ==========================================
def process_group_message(group_name, sender_name, sender_phone, raw_text):
    # 1. تحليل النص بالذكاء الاصطناعي
    parsed = call_ai_parser(raw_text)
    if not parsed or not parsed.get("is_trip_related"):
        return {"status": "ignored", "reason": "not_trip_related"}
        
    origin = parsed.get("origin")
    destination = parsed.get("destination")
    contact_phone = parsed.get("contact_phone") or sender_phone
    # تنظيف رقم الهاتف
    contact_phone = contact_phone.replace("+", "").replace(" ", "").strip()
    if not contact_phone.startswith("20") and contact_phone.startswith("1"):
        contact_phone = "20" + contact_phone
        
    date_time = parsed.get("date_time")
    
    # 2. فحص التكرار لمنع تكرار الإشعار في مجموعات مختلفة
    if is_duplicate(origin, destination, date_time, contact_phone):
        print(f"[Sniper] Message from {sender_phone} duplicate of recent trip {origin} -> {destination}. Ignored.")
        return {"status": "ignored", "reason": "duplicate"}
        
    # 3. فحص المطابقة مع الفلاتر النشطة
    is_matched = check_match(parsed)
    
    # 4. حفظ الرحلة المحللة في سوبابيز
    db_payload = {
        "group_name": group_name,
        "sender_name": sender_name,
        "raw_message": raw_text,
        "operation_type": parsed.get("operation_type"),
        "origin": origin,
        "destination": destination,
        "date_time": date_time,
        "price": parsed.get("price"),
        "car_type": parsed.get("car_type"),
        "contact_phone": contact_phone,
        "office_name": parsed.get("office_name"),
        "is_matched": is_matched
    }
    
    try:
        r = requests.post(f"{SUPABASE_URL}/rest/v1/sniper_parsed_trips", headers=HEADERS, json=db_payload, timeout=5)
        print(f"[Sniper] Saved parsed trip to DB (Match: {is_matched}). Code: {r.status_code}")
    except Exception as e:
        print(f"[Sniper DB Save Error]: {e}")
        
    # 5. إذا طابق الفلتر، إرسال إشعار فوري للتليجرام
    if is_matched:
        alert_msg = format_telegram_alert(db_payload)
        send_telegram_alert(alert_msg)
        print(f"[Sniper MATCH] Alert sent for {origin} -> {destination} ({contact_phone})")
        return {"status": "matched", "data": db_payload}
        
    return {"status": "parsed_but_no_match", "data": db_payload}
