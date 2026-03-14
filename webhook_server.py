from flask import Flask, request, jsonify, make_response, send_from_directory
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import json
import re
from datetime import datetime
import time
import ai_agent         # مخ الواتساب
import messenger_agent  # 🆕 مخ الماسنجر الجديد (تأكد من وجود الملف بجانبه)
import uuid
import os
import traceback

app = Flask(__name__)

# =====================================================
# 🌐 إعدادات CORS العالمية (Global CORS)
# =====================================================
@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,ngrok-skip-browser-warning')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# =====================================================
# 🗄️ إعدادات قاعدة البيانات (Supabase)
# =====================================================
SUPABASE_URL = 'https://wtjwzqvmwnbvjxnmweqq.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NjU0MDMsImV4cCI6MjA4NzA0MTQwM30.kTFK22b18cc1BmvMyLTt-7V113jyf_YrodSB7Km00tY'
SUPABASE_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

# ⚠️ مفتاح الـ Service Role لإنشاء الموظفين
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTQ2NTQwMywiZXhwIjoyMDg3MDQxNDAzfQ.WYNflQntWBCHXDnxFf2C1X1IerYZtMfMT6p6P4Dx0Vg'

# --- 🧠 حل مشكلة الأسماء تلقائياً ---
def resolve_sender_name(channel, sender_id, current_name=None):
    """
    محاولة جلب اسم العميل الحقيقي من عدة مصادر
    1. البحث في الرسائل السابقة عن اسم غير الرقم
    2. للواتساب: البحث في جدول الحجوزات (google_reservations)
    3. للماسنجر: استخدام Graph API
    """
    # إذا كان الاسم موجوداً وليس مجرد رقم ID أو اسم وهمي، نعيده فوراً
    if current_name and current_name not in [str(sender_id), "Admin", "ش"]:
        return current_name

    # مصدر 1: البحث في Supabase عن آخر اسم مسجل لهذا المستخدم
    try:
        url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages?sender_id=eq.{sender_id}&select=sender_name&order=created_at.desc&limit=1"
        r = requests.get(url, headers=SUPABASE_HEADERS)
        if r.status_code == 200:
            data = r.json()
            if data and data[0].get('sender_name') and data[0]['sender_name'] not in [str(sender_id), "ش", "Admin"]:
                return data[0]['sender_name']
    except: pass

    # مصدر 2: للواتساب (sender_id هو رقم الهاتف) - ابحث في الحجوزات
    if channel == 'whatsapp':
        try:
            # تنظيف الرقم للبحث (إزالة أي علامات + أو 00)
            clean_id = str(sender_id).replace('+', '').replace('00', '')
            if clean_id.startswith('20'): clean_id = clean_id[2:] # Remove Egypt country code for fuzzy match
            
            # 🛑 حماية: لا تبحث إذا كان الرقم قصيراً جداً (يمنع تطابق PSIDs مع بيانات اختبار قصيرة)
            if len(clean_id) < 8:
                 return current_name if current_name else str(sender_id)

            url = f"{SUPABASE_URL}/rest/v1/google_reservations?customer_phone=ilike.%{clean_id}%&select=customer_name&limit=1"
            r = requests.get(url, headers=SUPABASE_HEADERS)
            if r.status_code == 200:
                data = r.json()
                if data and data[0].get('customer_name'):
                    print(f"✅ Found Name in Reservations: {data[0]['customer_name']} for {sender_id}")
                    return data[0]['customer_name']
        except Exception as e:
            print(f"⚠️ resolve_sender_name (WA) Error: {e}")

    # مصدر 3: للماسنجر - استخدام Graph API
    if channel == 'messenger':
        return get_facebook_user_name(sender_id)

    return current_name if current_name else str(sender_id)

def insert_message_to_supabase(channel, sender_id, sender_name, message_text, is_from_admin=False):
    """إدراج الرسالة في صندوق الوارد الموحد في Supabase"""
    # تأكد من أن لدينا الاسم الحقيقي قبل الحفظ (إذا لم تكن الرسالة من الأدمن)
    if not is_from_admin:
        sender_name = resolve_sender_name(channel, sender_id, sender_name)

    url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages"
    data = {
        "channel": channel,
        "sender_id": str(sender_id),
        "sender_name": sender_name,
        "message_text": message_text,
        "is_from_admin": is_from_admin
    }
    try:
        response = requests.post(url, headers=SUPABASE_HEADERS, json=data)
        if response.status_code in [200, 201]:
            print(f"✅ تم حفظ رسالة {channel} في Supabase بنجاح!")
        else:
            print(f"❌ خطأ في حفظ الرسالة في Supabase: {response.text}")
    except Exception as e:
        print(f"❌ استثناء أثناء حفظ الرسالة في Supabase: {e}")

# =====================================================
# 🛠️ مساعدات (Helper Functions)
# =====================================================
WHATSAPP_TOKEN = "EAAPDbwUyvY0BQrm6ZB9qb62LU9hI50ZC9QOfZAO3VPA7ZCSnFSRMCb2kouBRkXu4LiVmRU2ydv1vLl00kKmgTFMN5ULJOpImor7i8oITjicjIjWiOLxTL7yltYrlF0RLxcdU6UNO4Ouv0BnQ79OK2sgSLpHY9ZCQs4iRIxcpjnoxr8EWpV4FSgGTzgZDZD"
PHONE_ID = "597129733493778"
VERIFY_TOKEN = "24seven_secret_token"
SHEET_NAME = "امر حجز عميل"
LOG_SHEET_NAME = "Chat_Logs"
FEEDBACK_SHEET_NAME = "تقييمات الموظفين"  # شيت التقييمات

# 🧠 ذاكرة الحالات (لتتبع الموظف والفيدباك)
messenger_states = {} 
messenger_feedback_data = {} 
user_state = {} 

# =====================================================
# 🆕 إعدادات الماسنجر (Messenger Config)
# =====================================================
FB_PAGE_TOKEN = "EAAPDbwUyvY0BQ3KLTieXWMHZAJZC92eQI9sBwEISipvaaVR9hoteMHWhx0fi8mSXIC4TnTiBHpykmsv6HyAkYK4yQUyQv81ZCF7EZA5CEZAKwPqhfl3jjmaN5muRSk1ZCpNh7OXAQ8Ey7ilMhBmjPvQpLRlzMD8MbYWChOdFxwiFKgPNAqJhg6aVZBR25rvIvChgw1vusjBwHZAeveEMSHpaQ9ps"
FB_VERIFY_TOKEN = "messenger_secret_24seven"

def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    return gspread.authorize(creds)

def get_sheet(sheet_name):
    client = get_client()
    return client.open_by_url('https://docs.google.com/spreadsheets/d/1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4/edit').worksheet(sheet_name)

def get_main_sheet():
    return get_sheet(SHEET_NAME)

def log_to_sheet(sheet_name, row_data):
    try:
        sheet = get_sheet(sheet_name)
        sheet.append_row(row_data)
    except: pass

def log_chat_to_sheet(phone, sender, message):
    try:
        client = get_client()
        try:
            sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4/edit').worksheet(LOG_SHEET_NAME)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sheet.append_row([timestamp, str(phone), sender, str(message)])
        except: pass
    except: pass

# =====================================================
# 🟢 الجزء الأول: وظائف الواتساب (WhatsApp Functions)
# =====================================================
def send_whatsapp_message(to, body_text):
    url = f"https://graph.facebook.com/v17.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    data = { "messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body_text} }
    try:
        requests.post(url, headers=headers, json=data)
        log_chat_to_sheet(to, "Bot", body_text)
    except Exception as e:
        print(f"❌ Exception Sending: {e}")

def send_location_request_template(to):
    url = f"https://graph.facebook.com/v17.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    data = { 
        "messaging_product": "whatsapp", 
        "to": to, 
        "type": "template", 
        "template": {"name": "location_request", "language": {"code": "ar"}} 
    }
    requests.post(url, headers=headers, json=data)
    log_chat_to_sheet(to, "Bot", "[Template: طلب لوكيشن]")

def clean_phone_strict(phone):
    """تنظيف الرقم للمطابقة مع الشيت - إزالة علامة الزائد والأصفار الزائدة"""
    if not phone: return ""
    clean = re.sub(r'\D', '', str(phone))
    if clean.startswith("00"): clean = clean[2:]
    # نعيد آخر 11 رقم (الموبايل المصري) أو الرقم كاملاً لو كان دولياً
    return clean[-11:] if len(clean) >= 11 else clean

def find_active_session(sheet, sender_phone):
    """البحث عن جلسة نشطة (تأكيد أو تقييم) بناءً على حالة الشيت"""
    try:
        clean_sender = clean_phone_strict(sender_phone)
        all_rows = sheet.get_all_values()
        
        # 1. فحص التقييم (Z = index 25) - له الأولوية لو أرسلنا تقييم
        for i in range(len(all_rows)-1, 0, -1):
            row = all_rows[i]
            if len(row) > 25:
                if clean_phone_strict(row[4]) == clean_sender and "طلب التقييم" in str(row[25]):
                    return i + 1, "feedback"
                    
        # 2. فحص التأكيد (AA = index 26) 
        for i in range(len(all_rows)-1, 0, -1):
            row = all_rows[i]
            if len(row) > 26:
                if clean_phone_strict(row[4]) == clean_sender and "طلب التأكيد" in str(row[26]):
                    return i + 1, "confirm"
        
        # fallback: آخر رحلة (لعمليات عامة)
        for i in range(len(all_rows)-1, 0, -1):
            row = all_rows[i]
            if len(row) > 4:
                if clean_phone_strict(row[4]) == clean_sender:
                    return i + 1, "unknown"
                    
        return -1, None
    except Exception as e:
        print(f"❌ خطأ في find_active_session: {e}")
        return -1, None

def find_active_row(sheet, sender_phone):
    row, _ = find_active_session(sheet, sender_phone)
    return row

def handle_confirmation(sender, text, row=None):
    sheet = get_main_sheet()
    if not row:
        row, stype = find_active_session(sheet, sender)
        if stype != "confirm": return # لا نعالج التأكيد لو الجلسة ليست "تأكيد"
        
    if row != -1:
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in ["تأكيد", "confirm", "نعم", "وافق", "ok", "yes", "تمام"]):
            print(f"📝 تسجيل الموافقة في AB{row}...")
            try:
                sheet.update_acell(f"AB{row}", "وافق ✅") 
                send_whatsapp_message(sender, "شكراً لتأكيدك 🌹\nمن فضلك اضغط الزر بالأسفل لمشاركة اللوكيشن 👇")
                time.sleep(1)
                send_location_request_template(sender)
            except Exception as e:
                print(f"❌ فشل الكتابة: {e}")
        elif any(keyword in text_lower for keyword in ["إلغاء", "cancel", "لا", "رفض", "no"]):
            try:
                sheet.update_acell(f"AB{row}", "رفض ❌")
                send_whatsapp_message(sender, "تم إلغاء الطلب بناءً على رغبتك.")
            except: pass

def handle_location_received(sender, msg):
    sheet = get_main_sheet()
    row = find_active_row(sheet, sender)
    if row != -1:
        lat = msg['location']['latitude']
        lng = msg['location']['longitude']
        maps_link = f"https://maps.google.com/maps?q={lat},{lng}"
        print(f"📝 تسجيل اللوكيشن في AC{row}...")
        try:
            sheet.update_acell(f"AC{row}", maps_link)
            print(f"✅ تم حفظ اللوكيشن في الصف {row}.")
            send_whatsapp_message(sender, "وصلنا اللوكيشن، شكراً لتعاونك! 🚗💨")
        except Exception as e:
            print(f"❌ فشل الكتابة في الشيت: {e}")

def start_feedback_flow(sender, text, row):
    """البدء في تسجيل التقييم (تسجيل أول إجابة: التقييم العام)"""
    sheet = get_main_sheet()
    try:
        # 1. تسجيل التقييم العام في AD (Column 30)
        sheet.update_acell(f"AD{row}", text)
        # 2. تحديث الحالة في Z لكي لا نكرر البدء
        sheet.update_acell(f"Z{row}", "جاري التقييم... ⏳")
        # 3. حفظ الحالة في الذاكرة
        user_state[sender] = {"step": "q2", "row": row, "timestamp": time.time()}
        send_whatsapp_message(sender, "س2: هل كانت السيارة نظيفة؟ (نعم / لا)")
    except Exception as e:
        print(f"❌ فشل start_feedback_flow: {e}")

def handle_feedback_flow(sender, text):
    state = user_state[sender]
    step = state['step']
    row = state['row']
    sheet = get_main_sheet()
    try:
        if step == "q2":
            sheet.update_acell(f"AE{row}", text)
            user_state[sender]['step'] = "q3"
            send_whatsapp_message(sender, "س3: تقييمك للكابتن؟ (مثلاً: ممتاز، جيد، ..)")
        elif step == "q3":
            sheet.update_acell(f"AF{row}", text)
            user_state[sender]['step'] = "q4"
            send_whatsapp_message(sender, "س4: هل ترشحنا لأقاربك؟ (نعم / لا)")
        elif step == "q4":
            sheet.update_acell(f"AG{row}", text)
            user_state[sender]['step'] = "q5"
            send_whatsapp_message(sender, "س5: (اختياري) هل لديك أي اقتراحات؟")
        elif step == "q5":
            sheet.update_acell(f"AH{row}", text)
            # تحديث الحالة النهائية في الشيت
            sheet.update_acell(f"Z{row}", "تم انتهاء التقييم ✅")
            user_state.pop(sender, None)
            send_whatsapp_message(sender, "شكراً لملاحظاتك ❤️، دمت بودنا.")
    except Exception as e:
        print(f"❌ فشل حفظ التقييم: {e}")

# =====================================================
# 🚀 نقطة استقبال الواتساب (Endpoint: /webhook)
# =====================================================
@app.route('/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Error", 403

    if request.method == 'POST':
        data = request.json
        try:
            if data.get('entry'):
                changes = data['entry'][0]['changes'][0]['value']
                if 'messages' in changes:
                    msg = changes['messages'][0]
                    sender = msg['from']
                    msg_type = msg['type']
                    
                    text_body = ""
                    if msg_type == 'text': text_body = msg['text']['body']
                    elif msg_type == 'interactive': 
                        if 'button_reply' in msg['interactive']: text_body = msg['interactive']['button_reply']['title']
                        elif 'list_reply' in msg['interactive']: text_body = msg['interactive']['list_reply']['title']
                    elif msg_type == 'button': text_body = msg['button']['text']
                    elif msg_type == 'location': 
                        text_body = "LOCATION_SHARED"
                        # 📍 معالجة اللوكيشن برمجياً
                        handle_location_received(sender, msg)
                    
                    print(f"📩 (WA) رسالة من {sender}: {text_body}")
                    log_chat_to_sheet(sender, "Client", text_body)

                    # 1. إدراج في Supabase للمحادثات
                    insert_message_to_supabase(
                        channel='whatsapp',
                        sender_id=sender,
                        sender_name=sender, 
                        message_text=text_body,
                        is_from_admin=False
                    )

                    # 2. المعالجة البرمجية (تأكيد الحجز / تقييم)
                    if sender in user_state:
                         handle_feedback_flow(sender, text_body)
                    elif msg_type in ['text', 'button', 'interactive']:
                         # فحص هل هناك جلسة نشطة منتظرة رد (تأكيد أو تقييم في الشيت)
                         sheet = get_main_sheet()
                         row_idx, session_type = find_active_session(sheet, sender)
                         
                         if session_type == "feedback":
                              start_feedback_flow(sender, text_body, row_idx)
                         elif session_type == "confirm":
                              handle_confirmation(sender, text_body, row_idx)
                    
        except Exception as e:
            print(f"❌ Webhook Error: {e}")
            traceback.print_exc()
        return "OK", 200


# =====================================================
# 🔵 الجزء الثاني: وظائف الماسنجر (Messenger Functions)
# =====================================================
def send_messenger_msg(recipient_id, text, quick_replies=None, buttons=None):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_TOKEN}"
    headers = {"Content-Type": "application/json"}
    
    if buttons:
        # استخدام Button Template (تكون ثابتة في الشات)
        msg_payload = {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text,
                    "buttons": [
                        {
                            "type": "postback" if b.get("payload") else "web_url",
                            "title": b["title"],
                            **({"payload": b["payload"]} if b.get("payload") else {"url": b.get("url", "")})
                        } for b in buttons
                    ]
                }
            }
        }
    else:
        msg_payload = {"text": text}

    # إضافة أزرار عائمة (Quick Replies) لو وجدت، سواء مع النص أو التمبلت
    if quick_replies:
        msg_payload["quick_replies"] = [
            {
                "content_type": "text",
                "title": qr["title"],
                "payload": qr["payload"]
            } for qr in quick_replies
        ]
        
    data = { "recipient": {"id": recipient_id}, "message": msg_payload }
    try:
        r = requests.post(url, headers=headers, json=data)
        if r.status_code == 200: print(f"✅ (FB) تم الرد على {recipient_id}")
        else: print(f"❌ (FB) فشل الرد: {r.text}")
    except: pass

def get_facebook_user_name(sender_id):
    """
    استدعاء Graph API لجلب اسم المستخدم من ماسنجر بناءً على الـ PSID
    """
    parameters = {
        "fields": "first_name,last_name",
        "access_token": FB_PAGE_TOKEN
    }
    url = f"https://graph.facebook.com/v18.0/{sender_id}"
    
    try:
        r = requests.get(url, params=parameters)
        if r.status_code == 200:
            data = r.json()
            first = data.get('first_name', '')
            last = data.get('last_name', '')
            name = f"{first} {last}".strip()
            if name:
                print(f"👤 Found FB Name: {name} (ID: {sender_id})")
                return name
        elif r.status_code == 400:
            # 💡 Permission issue (App Review needed)
            # print(f"ℹ️ Cannot fetch FB name for {sender_id} yet (App Review required).") 
            return "Messenger User" # Friendly placeholder
        else:
            print(f"❌ FB Graph API Error ({r.status_code}) for {sender_id}: {r.text}")
    except Exception as e:
        print(f"🔥 Exception in get_facebook_user_name for {sender_id}: {e}")
    
    return "Messenger User"

def handle_messenger_feedback_flow(sender_id, text):
    """
    دالة إدارة خطوات الفيدباك (س1 -> س2 -> س3 -> حفظ)
    """
    current_step = messenger_states.get(sender_id)
    
    if sender_id not in messenger_feedback_data:
        messenger_feedback_data[sender_id] = {"date": datetime.now().strftime("%Y-%m-%d %H:%M")}

    if current_step == "FB_Q1":
        messenger_feedback_data[sender_id]['rating'] = text
        messenger_states[sender_id] = "FB_Q2"
        send_messenger_msg(sender_id, "2️⃣ هل الموظف ساعدك في حل استفسارك؟ (نعم / لا)")
    
    elif current_step == "FB_Q2":
        messenger_feedback_data[sender_id]['helped'] = text
        messenger_states[sender_id] = "FB_Q3"
        send_messenger_msg(sender_id, "3️⃣ أخيراً.. هل عندك أي اقتراح لتطوير الموظف؟ (لو مفيش اكتب 'لا')")
    
    elif current_step == "FB_Q3":
        messenger_feedback_data[sender_id]['suggestion'] = text
        
        # حفظ البيانات في الشيت
        data = messenger_feedback_data[sender_id]
        row_to_save = [data['date'], sender_id, data.get('rating'), data.get('helped'), data.get('suggestion')]
        log_to_sheet(FEEDBACK_SHEET_NAME, row_to_save)
        
        # إعادة العميل للوضع الطبيعي
        messenger_states[sender_id] = "BOT" 
        send_messenger_msg(sender_id, "شكراً لوقتك وتقييمك! ❤️\nأنا رجعت معاك تاني (الرد الآلي) لأي استفسار جديد.")
        del messenger_feedback_data[sender_id]

# =====================================================
# 🚀 نقطة استقبال الماسنجر (Endpoint: /messenger)
# =====================================================
import threading
processed_mids = set() # ذاكرة مؤقتة لتخزين معرفات الرسائل المعالجة

def process_message_async(sender_id, text, user_profile):
    """
    دالة تعمل في الخلفية لمعالجة المنطق الثقيل (الذكاء الاصطناعي)
    دون تعطيل الرد على فيسبوك.
    """
    try:
        print(f"🔄 (Async) جاري معالجة رسالة من {sender_id}...")
        
        # معرفة حالة العميل الحالية
        current_state = messenger_states.get(sender_id, "BOT")

        # أ) حالة التحدث مع موظف (HUMAN)
        if current_state == "HUMAN":
            print(f"🤐 البوت صامت (وضع الموظف) للعميل {sender_id}")
            return # لا نرد، نترك الموظف يرد

        # ب) حالة الفيدباك (FEEDBACK)
        elif current_state.startswith("FB_"):
            handle_messenger_feedback_flow(sender_id, text)

        # ج) الحالة الطبيعية (BOT - AI)
        else:
            print(f"📩 (FB AI) تم استلام رسالة ولكن الذكاء الاصطناعي متوقف: {text}")

    except Exception as e:
        print(f"❌ Async Error: {e}")

@app.route('/messenger', methods=['GET', 'POST'])
def messenger_webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Error", 403

    if request.method == 'POST':
        data = request.json
        try:
            if data['object'] == 'page':
                for entry in data['entry']:
                    if 'messaging' not in entry:
                         continue
                         
                    for event in entry['messaging']:
                        if 'delivery' in event or 'read' in event:
                            continue

                        sender_id = event['sender']['id']
                        text = None
                        mid = event.get('message', {}).get('mid')
                        
                        # --- 🛡️ منع التكرار الموحد (بما في ذلك الـ Echoes) ---
                        if mid:
                            if mid in processed_mids:
                                print(f"⏭️ Skipping duplicate Messenger MID: {mid}")
                                continue
                            processed_mids.add(mid)
                            if len(processed_mids) > 10000: processed_mids.clear()

                        if 'message' in event:
                            if event['message'].get('is_echo'):
                                admin_text = event['message'].get('text', '').strip()
                                target_user_id = event['recipient']['id']
                                
                                print(f"📩 (FB App Echo) رسالة من الإدمن إلى {target_user_id}: {admin_text}")
                                insert_message_to_supabase(
                                    channel='messenger',
                                    sender_id=target_user_id,
                                    sender_name="Admin", 
                                    message_text=admin_text,
                                    is_from_admin=True
                                )
                                continue

                            if 'quick_reply' in event['message']:
                                text = event['message']['quick_reply'].get('payload')
                            elif 'text' in event['message']:
                                text = event['message']['text']
                        
                        elif 'postback' in event:
                            text = event['postback'].get('payload')
                            # Postbacks often don't have mid, use timestamp as surrogate
                            mid = f"pb_{sender_id}_{event.get('timestamp')}_{text}"
                            if mid in processed_mids: continue
                            processed_mids.add(mid)

                        if not text:
                            continue

                        user_profile = event.get('sender', {})
                        sender_name = f"{user_profile.get('first_name', '')} {user_profile.get('last_name', '')}".strip()
                        
                        if not sender_name:
                            sender_name = get_facebook_user_name(sender_id)

                        print(f"📩 (FB) رسالة من {sender_id}: {text}")
                        insert_message_to_supabase(
                            channel='messenger',
                            sender_id=sender_id,
                            sender_name=sender_name,
                            message_text=text,
                            is_from_admin=False
                        )

                        thread = threading.Thread(target=process_message_async, args=(sender_id, text, user_profile))
                        thread.start()
                                
        except Exception as e:
            print(f"❌ Messenger Error: {e}")
        
        return "EVENT_RECEIVED", 200

# =====================================================
# 🚀 API نقطة الإرسال الجديدة (Omnichannel Reply)
# =====================================================
@app.route('/api/send_reply', methods=['POST', 'OPTIONS'])
def send_omnichannel_reply():
    if request.method == 'OPTIONS':
        return make_response("", 204)

    data = request.json
    channel = data.get('channel', '').lower()
    sender_id = data.get('sender_id')
    message = data.get('message')

    if not channel or not sender_id or not message:
        return jsonify({"status": "error", "message": "Missing parameters"}), 400

    if channel == 'whatsapp':
        url = f"https://graph.facebook.com/v17.0/{PHONE_ID}/messages"
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
        payload = {"messaging_product": "whatsapp", "to": sender_id, "type": "text", "text": {"body": message}}
        try:
            requests.post(url, headers=headers, json=payload)
        except Exception as e:
            print(f"❌ WA Send Exception: {e}")

    elif channel == 'messenger':
        if not FB_PAGE_TOKEN:
            print("⚠️ FB_PAGE_TOKEN is empty.")
        else:
            url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_TOKEN}"
            headers = {"Content-Type": "application/json"}
            payload = {"recipient": {"id": sender_id}, "message": {"text": message}}
            try:
                requests.post(url, headers=headers, json=payload)
            except Exception as e:
                print(f"❌ Messenger Send Exception: {e}")
    else:
        return jsonify({"status": "error", "message": "Invalid channel type"}), 400

    # --- 🛡️ حفظ نسخة للواتساب يدوياً (لعدم ضمان وصول الـ Echo) ---
    if channel == 'whatsapp':
        insert_message_to_supabase(
            channel='whatsapp',
            sender_id=sender_id,
            sender_name="Admin",
            message_text=message,
            is_from_admin=True
        )
    # ملاحظة: للمسنجر نكتفي بالـ Echo الذي يصلنا من فيسبوك للتأكد من الوصول وتجنب التكرار.
    
    print(f"📤 Sent {channel} message to {sender_id}")

    response = jsonify({"status": "success"})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

# =====================================================
# 🛡️ إدارة الموظفين: إنشاء حساب جديد (Staff Management)
# =====================================================
@app.route('/admin/create-staff', methods=['POST', 'OPTIONS'])
def create_staff_account():
    if request.method == 'OPTIONS':
        return make_response("", 204)

    import os, traceback
    try:
        data = request.json
        email = data.get("email")
        password = data.get("password")
        full_name = data.get("full_name")
        role = data.get("role", "moderator")

        print(f"👤 Creating staff: {email} ({full_name}) as {role}")

        service_key = SUPABASE_SERVICE_ROLE_KEY
        if not service_key:
            error_msg = "❌ Missing SUPABASE_SERVICE_ROLE_KEY! Please set it in webhook_server.py line 20."
            print(error_msg)
            return jsonify({"status": "error", "detail": error_msg}), 500

        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json"
        }

        auth_url = f"{SUPABASE_URL}/auth/v1/admin/users"
        auth_data = {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"full_name": full_name, "role": role}
        }

        print("📡 Sending request to Supabase Auth Admin API...")
        r_auth = requests.post(auth_url, headers=headers, json=auth_data)
        
        if r_auth.status_code not in [200, 201]:
            detail = r_auth.text
            try: detail = r_auth.json().get('msg', r_auth.text)
            except: pass
            print(f"❌ Supabase Auth Error ({r_auth.status_code}): {detail}")
            return jsonify({"status": "error", "detail": f"Auth Error: {detail}"}), r_auth.status_code
        
        user_info = r_auth.json()
        user_id = user_info.get("id")
        print(f"✅ User created in Auth (ID: {user_id}). Creating profile...")

        profile_url = f"{SUPABASE_URL}/rest/v1/profiles"
        profile_data = {
            "id": user_id,
            "full_name": full_name,
            "role": role,
            "email": email
        }
        r_prof = requests.post(profile_url, headers=headers, json=profile_data)
        
        if r_prof.status_code not in [200, 201, 204]:
            print(f"⚠️ Profile creation warning ({r_prof.status_code}): {r_prof.text}")

        print(f"🎉 Staff account {email} created successfully!")
        return jsonify({"status": "success", "user_id": user_id})

    except Exception as e:
        print("🔥 Critical Error in create_staff_account:")
        traceback.print_exc()
        return jsonify({"status": "error", "detail": str(e)}), 500

# =====================================================
# 🔍 دالة فحص اتصال فيسبوك (Diagnostic)
# =====================================================
@app.route('/debug/fb')
def debug_fb():
    if not FB_PAGE_TOKEN: return jsonify({"error": "No token"}), 400
    try:
        # 1. جلب بيانات الصفحة والـ ID التابع لها
        url_me = f"https://graph.facebook.com/v18.0/me?access_token={FB_PAGE_TOKEN}"
        r_me = requests.get(url_me)
        page_data = r_me.json()
        page_id = page_data.get('id')
        
        # 2. فحص الصلاحيات باستخدام الـ Page ID صراحة
        perms_data = {}
        if page_id:
            perms_url = f"https://graph.facebook.com/v18.0/{page_id}/permissions?access_token={FB_PAGE_TOKEN}"
            pr = requests.get(perms_url)
            perms_data = pr.json()
        
        return jsonify({
            "page_info": page_data,
            "permissions": perms_data.get('data', perms_data),
            "debug_note": "If pages_messaging is not in the list below, you need App Review."
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================================
# 📂 خدمة الملفات (Static File Serving)
# =====================================================
@app.route('/<path:filename>')
def serve_any_file(filename):
    directory = os.path.join(os.getcwd(), '24Seven_SaaS_Platform')
    # تأكد أن الملف موجود لتجنب تداخل الروابط
    if os.path.isfile(os.path.join(directory, filename)):
        return send_from_directory(directory, filename)
    # إذا لم يكن ملفاً، قد يكون رابطاً للفلاسك نفسه، نتركه يمر للفلاسك الطبيعي
    return "Not Found", 404

@app.route('/moderator')
def serve_moderator():
    directory = os.path.join(os.getcwd(), '24Seven_SaaS_Platform')
    return send_from_directory(directory, 'moderator.html')

# =====================================================
# 🚀 تشغيل السيرفر الموحد
# =====================================================
@app.route('/api/health', methods=['GET', 'OPTIONS'])
def health_check():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    return jsonify({"status": "ok", "message": "Server is running"})

@app.route('/ping')
def ping():
    return "pong"

if __name__ == '__main__':
    print("🚀 Server Started on Port 3000 (Handling Both WhatsApp & Messenger & API Replies)...")
    app.run(host='0.0.0.0', port=3000)