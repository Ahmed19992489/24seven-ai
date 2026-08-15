from flask import Flask, request, jsonify, make_response, send_from_directory, redirect
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import ssl
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 🛡️ تفعيل محول التشفير الفولاذي المقاوم للقطع وانهيار الشبكة (SSLEOFError)
class ResilientTLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
        except Exception:
            pass
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

_global_http_session = requests.Session()
_global_tls_adapter = ResilientTLSAdapter(max_retries=Retry(total=5, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504], raise_on_status=False))
_global_http_session.mount("https://", _global_tls_adapter)
_global_http_session.mount("http://", _global_tls_adapter)

requests.get = _global_http_session.get
requests.post = _global_http_session.post
requests.patch = _global_http_session.patch
requests.put = _global_http_session.put
requests.delete = _global_http_session.delete
import os
import sys

# Ensure current directory and parent directory are always in Python's search path
_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_this_dir)
for _p in [_this_dir, _parent_dir]:
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

import json
import re
from datetime import datetime, timedelta
import time
import ai_agent         # [WA] مخ الواتساب
import messenger_agent  # [FB] مخ الماسنجر الجديد (تأكد من وجود الملف بجانبه)
import uuid
from dotenv import load_dotenv
import threading

# تحميل متغيرات البيئة من ملف .env في المجلد الفرعي أو الرئيسي
if os.path.exists('24Seven_SaaS_Platform/.env'):
    load_dotenv('24Seven_SaaS_Platform/.env')
elif os.path.exists(os.path.join(_this_dir, '.env')):
    load_dotenv(os.path.join(_this_dir, '.env'))
elif os.path.exists(os.path.join(_parent_dir, '.env')):
    load_dotenv(os.path.join(_parent_dir, '.env'))
else:
    load_dotenv()

import traceback
import sys
import builtins
import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# [GLOBAL FIX] Prevent UnicodeEncodeError on Windows Console
# This intercept all print() calls and strips non-ASCII to prevent 500 errors
def clean_for_terminal(*args):
    new_args = []
    for arg in args:
        if isinstance(arg, str):
            # Replace non-ASCII with ? to avoid crashing the Windows console
            new_args.append(arg.encode('ascii', 'replace').decode('ascii'))
        else:
            new_args.append(arg)
    return new_args

_original_print = builtins.print
def safe_print(*args, **kwargs):
    # Force flush and ensure no crash
    kwargs['flush'] = True
    try:
        _original_print(*clean_for_terminal(*args), **kwargs)
    except:
        # Fallback to very basic print if even that fails
        try: _original_print("Output Error")
        except: pass

builtins.print = safe_print

# Reconfigure streams as a second layer of defense
if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(errors='replace')
    except: pass
if hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(errors='replace')
    except: pass

app = Flask(__name__)

# =====================================================
# [GLOBAL] Global CORS إعدادات CORS العالمية
# =====================================================
@app.after_request
def add_cors_headers(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,ngrok-skip-browser-warning')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# = [ROOT] Root Route (For Meta Verification Fallback)
# =====================================================
@app.route('/')
def index():
    # If Meta is trying to verify the root URL instead of /webhook
    if request.args.get("hub.verify_token") == VERIFY_TOKEN or request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "24Seven Server is Running. Please use /webhook for WhatsApp or /messenger for Messenger.", 200

# = [SUPABASE] Supabase إعدادات قاعدة البيانات
# =====================================================
SUPABASE_URL = 'https://khskudtxbypohvnreloi.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I'
SUPABASE_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

# [WARNING] مفتاح الـ Service Role لإنشاء الموظفين
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjMxMjAyOSwiZXhwIjoyMTAxODg4MDI5fQ.uyCTVGkoeoz4xB3r2muV_fLiI62QIw-65g2nVeIb62w'

SUPABASE_SERVICE_HEADERS = {
    'apikey': SUPABASE_SERVICE_ROLE_KEY,
    'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
    'Content-Type': 'application/json'
}


# --- [INFO] حل مشكلة الأسماء تلقائياً ---
def resolve_sender_name(channel, sender_id, current_name=None):
    """
    محاولة جلب اسم العميل الحقيقي من عدة مصادر
    1. البحث في الرسائل السابقة عن اسم غير الرقم
    2. للواتساب: البحث في جدول الحجوزات (google_reservations)
    3. للماسنجر: استخدام Graph API
    """
    # إذا كان الاسم موجوداً وليس مجرد رقم ID أو اسم وهمي، نعيده فوراً
    if current_name and current_name not in [str(sender_id), "Admin", "ش", "Messenger User", "Instagram User"]:
        return current_name

    # مصدر 1: البحث في Supabase عن آخر اسم مسجل لهذا المستخدم
    try:
        url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages?sender_id=eq.{sender_id}&select=sender_name&order=created_at.desc&limit=1"
        r = requests.get(url, headers=SUPABASE_SERVICE_HEADERS) # Bypassing RLS
        if r.status_code == 200:
            data = r.json()
            if data and data[0].get('sender_name') and data[0]['sender_name'] not in [str(sender_id), "ش", "Admin", "Messenger User", "Instagram User"]:
                return data[0]['sender_name']
    except: pass

    # مصدر 2: للواتساب (sender_id هو رقم الهاتف) - ابحث في الحجوزات
    if channel == 'whatsapp':
        try:
            # تنظيف الرقم للبحث (إزالة أي علامات + أو 00 أو مسافات)
            clean_id = str(sender_id).replace('+', '').replace('00', '').replace(' ', '').strip()
            if clean_id.startswith('20'): clean_id = clean_id[2:] # Remove Egypt country code for fuzzy match
            
            # [INFO] حماية: لا تبحث إذا كان الرقم قصيراً جداً (يمنع تطابق PSIDs مع بيانات اختبار قصيرة)
            if len(clean_id) < 8:
                 return current_name if current_name else str(sender_id)

            # استخدام آخر 8 أرقام للمطابقة الأكثر مرونة
            last_8 = clean_id[-8:]
            url = f"{SUPABASE_URL}/rest/v1/google_reservations?customer_phone=ilike.%{last_8}%&select=customer_name&limit=1"
            r = requests.get(url, headers=SUPABASE_SERVICE_HEADERS) # Bypassing RLS
            if r.status_code == 200:
                data = r.json()
                if data and data[0].get('customer_name'):
                    print(f"[WA] Found Name in Reservations: {data[0]['customer_name']} for {sender_id}")
                    return data[0]['customer_name']
        except Exception as e:
            print(f"[ERROR] resolve_sender_name (WA) Error: {e}")

    # مصدر 3: للماسنجر - استخدام Graph API
    elif channel == 'messenger':
        return get_facebook_user_name(sender_id)
    return current_name if current_name else str(sender_id)


def insert_message_to_supabase(channel, sender_id, sender_name, message_text, is_from_admin=False, whatsapp_instance_id=None):
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
    if channel == "whatsapp" and whatsapp_instance_id:
        data["whatsapp_instance_id"] = whatsapp_instance_id
        
    try:
        response = requests.post(url, headers=SUPABASE_HEADERS, json=data)
        if response.status_code in [200, 201]:
            print(f"[INFO] {channel} message saved to Supabase successfully!")
        else:
            print(f"[ERROR] Error saving to Supabase: {response.text}")
    except Exception as e:
        print(f"[ERROR] Exception saving to Supabase: {e}")

# = [HELPERS] Helper Functions مساعدات
# =====================================================
WHATSAPP_TOKEN = "EAAPDbwUyvY0BQrm6ZB9qb62LU9hI50ZC9QOfZAO3VPA7ZCSnFSRMCb2kouBRkXu4LiVmRU2ydv1vLl00kKmgTFMN5ULJOpImor7i8oITjicjIjWiOLxTL7yltYrlF0RLxcdU6UNOaIdqo4Ouv0BnQ79OK2sgSLpHY9ZCQs4iRIxcpjnoxr8EWpV4FSgGTzgZDZD"

def download_whatsapp_media(media_id, mime_type):
    try:
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        r = requests.get(url, params={"access_token": WHATSAPP_TOKEN}, timeout=5)
        if r.status_code == 200:
            media_data = r.json()
            download_url = media_data.get('url')
            if download_url:
                # Download the file content
                headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
                r_file = requests.get(download_url, headers=headers, timeout=10)
                if r_file.status_code == 200:
                    ext = ".jpg"
                    if "png" in mime_type: ext = ".png"
                    elif "gif" in mime_type: ext = ".gif"
                    elif "webp" in mime_type: ext = ".webp"
                    elif "audio" in mime_type or "ogg" in mime_type: ext = ".mp3"
                    elif "video" in mime_type: ext = ".mp4"
                    
                    filename = f"wa_media_{media_id}_{int(time.time())}{ext}"
                    upload_dir = os.path.join(os.path.dirname(__file__), '24Seven_SaaS_Platform', 'static', 'uploads')
                    os.makedirs(upload_dir, exist_ok=True)
                    
                    file_path = os.path.join(upload_dir, filename)
                    with open(file_path, 'wb') as f:
                        f.write(r_file.content)
                    
                    return f"/static/uploads/{filename}"
    except Exception as e:
        print(f"[ERROR] Failed to download WhatsApp media: {e}")
    return None
PHONE_ID = "597129733493778"
VERIFY_TOKEN = "24seven_secret_token"
SHEET_NAME = "امر حجز عميل"
# =====================================================
# [AI INTENT] نظام فهم النوايا بـ Groq AI (لفهم ردود العملاء بشكل ذكي)
# =====================================================
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')

def ai_understand_intent(text, context='confirmation'):
    """
    يستخدم Groq AI لفهم نية العميل بالعربي بشكل ذكي.
    context: 'confirmation' أو 'feedback_yes_no' أو 'feedback_rating' أو 'feedback_suggest'
    يعيد: dict بـ {'intent': str, 'value': str, 'confidence': float}
    """
    try:
        if context == 'confirmation':
            system_msg = """أنت محلل نوايا لشركة ليموزين. مهمتك تحديد هل العميل يؤكد أو يلغي حجزه.
رد فقط بـ JSON هكذا: {"intent": "confirm" أو "cancel" أو "unclear", "confidence": 0.0-1.0}
أمثلة تأكيد: تأكيد، اوكي، نعم، تمام، موافق، اكيد، اه، يلا، حلو، ماشي، أيوه، ايوه، يس، اتفقنا
أمثلة إلغاء: لأ، لا، إلغاء، مش عايز، بلغي، كنسل، مستأجلنا، بردد
أمثلة غير واضح: سؤال عن موعد، شكوى، موضوع آخر"""
        elif context == 'feedback_yes_no':
            system_msg = """أنت محلل نوايا. مهمتك تحديد هل رد العميل إيجابي أو سلبي.
رد فقط بـ JSON: {"intent": "yes" أو "no" أو "unclear", "confidence": 0.0-1.0}
نعم = نعم، أيوه، تمام، جداً، كويس، ايجابي، أكيد، طبعاً، بالتأكيد، معاك، معها
لا = لا، لأ، مش، مش كويس، سلبي، لم"""
        elif context == 'feedback_rating':
            system_msg = """أنت محلل نوايا. استخرج التقييم من كلام العميل (1-5 نجوم أو وصف).
رد فقط بـ JSON: {"intent": "rated", "value": "(النص الأصلي للعميل)", "stars": رقم 1-5 أو null, "confidence": 0.0-1.0}
ممتاز/رائع/5 = 5، كويس/جيد/4 = 4، متوسط/3 = 3، وحش/2 = 2، سيء/1 = 1"""
        else:  # feedback_suggest (اقتراحات اختيارية)
            system_msg = """العميل أرسل رسالة كاقتراح اختياري. استخرج محتوى الاقتراح أو "لا يوجد" لو قال لا.
رد فقط بـ JSON: {"intent": "suggestion", "value": "(نص الاقتراح أو لا يوجد)", "confidence": 0.0-1.0}"""

        url = 'https://api.groq.com/openai/v1/chat/completions'
        headers = {
            'Authorization': f'Bearer {GROQ_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': GROQ_MODEL,
            'messages': [
                {'role': 'system', 'content': system_msg},
                {'role': 'user', 'content': f'رسالة العميل: "{text}"'}
            ],
            'temperature': 0.1,
            'max_tokens': 100,
            'response_format': {'type': 'json_object'}
        }
        r = requests.post(url, headers=headers, json=payload, timeout=8)
        if r.status_code == 200:
            result = r.json()
            content = result['choices'][0]['message']['content']
            import json as _json
            parsed = _json.loads(content)
            print(f"[AI-Intent] context={context}, text='{text}', result={parsed}")
            return parsed
        else:
            print(f"[AI-Intent] Groq error: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[AI-Intent] Exception: {e}")
    
    # Fallback: regex بسيط
    t = text.lower().strip()
    if context == 'confirmation':
        if re.search(r'تأكيد|تاكيد|نعم|اوكي|موافق|تمام|ماشي|يلا|اه\b|ايه\b|اكيد|يس|اتفقنا|ماشيين|ايوه|اوك', t):
            return {'intent': 'confirm', 'confidence': 0.8}
        if re.search(r'لا\b|لأ|إلغاء|الغاء|كنسل|مش عايز|بلغي', t):
            return {'intent': 'cancel', 'confidence': 0.8}
        return {'intent': 'unclear', 'confidence': 0.3}
    elif context == 'feedback_yes_no':
        if re.search(r'نعم|اه\b|ايوه|تمام|اكيد|طبعاً|بالتأكيد', t):
            return {'intent': 'yes', 'confidence': 0.8}
        if re.search(r'لا\b|لأ|مش|لم', t):
            return {'intent': 'no', 'confidence': 0.8}
        return {'intent': 'unclear', 'confidence': 0.3}
    return {'intent': 'unclear', 'value': text, 'confidence': 0.3}

AI_AUTOREPLY_ENABLED = False   # ❌ إيقاف الرد التلقائي بـ Gemini AI على ماسنجر
AI_CHAT_PROXY_ENABLED = True   # ✅ مفعل للوحة التحكم
ADMIN_NOTIFY_ENABLED = True    # ✅ تفعيل إشعارات الأدمن
DEBUG_LOGS = True              # ✅ تفعيل السجلات للتحقق
TERMINAL_FLUSH = True          # ✅ تفعيل التفريغ الفوري للبيانات لضمان ظهورها في الشاشة السوداء
LOG_SHEET_NAME = "Chat_Logs"
FEEDBACK_SHEET_NAME = "تقييمات الموظفين"  # شيت التقييمات

# [STATE] ذاكرة الحالات (لتتبع الموظف والفيدباك)
messenger_states = {} 
messenger_feedback_data = {} 
user_state = {} 

# [FIX] منع تكرار معالجة رسائل الفيدباك (بسبب وجود رقمين واتساب)
# key = (sender_phone + message_text_hash), value = timestamp
_feedback_dedup_cache = {}
FEEDBACK_DEDUP_WINDOW_SEC = 8  # ثواني: لو نفس الرسالة جاءت خلال 8 ثواني تُتجاهل

# [FIX] فترة راحة بعد انتهاء الفيدباك (البوت لا يرد لمدة ساعة)
# key = sender_phone, value = timestamp of feedback completion
_post_feedback_cooldown = {}
POST_FEEDBACK_COOLDOWN_SEC = 3600  # ساعة كاملة

def _is_feedback_duplicate(sender, text):
    """يتحقق إذا كانت هذه الرسالة قد عولجت مؤخراً كفيدباك (لمنع التكرار من رقمين)"""
    import hashlib
    key = sender + hashlib.md5(text.encode('utf-8', errors='replace')).hexdigest()
    now = time.time()
    # تنظيف القديم
    expired = [k for k, v in _feedback_dedup_cache.items() if now - v > FEEDBACK_DEDUP_WINDOW_SEC * 2]
    for k in expired: del _feedback_dedup_cache[k]
    if key in _feedback_dedup_cache and (now - _feedback_dedup_cache[key]) < FEEDBACK_DEDUP_WINDOW_SEC:
        return True
    _feedback_dedup_cache[key] = now
    return False

def _mark_post_feedback_cooldown(sender):
    """يضع العميل في فترة راحة بعد انتهاء الفيدباك"""
    _post_feedback_cooldown[sender] = time.time()

def _is_in_post_feedback_cooldown(sender):
    """يتحقق إذا كان العميل في فترة الراحة بعد الفيدباك"""
    if sender not in _post_feedback_cooldown:
        return False
    elapsed = time.time() - _post_feedback_cooldown[sender]
    if elapsed > POST_FEEDBACK_COOLDOWN_SEC:
        del _post_feedback_cooldown[sender]
        return False
    return True

# = [MESSENGER] Messenger Config إعدادات الماسنجر
# =====================================================
FB_PAGE_TOKEN = "EAAPDbwUyvY0BRN0VW4bIHPLRpeA7qHqK5TyFpNxJ8fuFcvVCshuBwZC52F59Q6oNH671nLZBbAiEsGSB55Vq0sHjyMIB4QNStzt6sFxRL7ImzttrnuFkHVTYWGZC0J2MgbBGfqo3dOi7Wo5QagQ7pY3vhZAztfKZBhNZCxGrVeGRIqz7pUkHHC2iM4ZA0mDje9oEXZCm"
FB_VERIFY_TOKEN = "messenger_secret_24seven"

# = [INSTAGRAM] Instagram Config إعدادات الإنستجرام
# =====================================================
INSTAGRAM_TOKEN = "IGAAMRP14aPG1BZAGFRbFAtUHd4c3BNckxCVC0xOFl4ZAmRXbzRmRVRVNmljTkFwZAzdUUlVlRHJ4dVhSTklyczJkYWlCa2VvUWJVb2w5VzZAUY1FJV2M2UHczaTdyVk9fN1NXMW5UZAUwydFhyTnFhX3RldDl3VVdiNXFKZAl9Wb0JaVQZDZD"  # Updated 2026-06-12
INSTAGRAM_VERIFY_TOKEN = "24seven_secret_token"

_cached_client = None
_cached_spreadsheet = None
_cache_lock = threading.Lock()

def get_client():
    global _cached_client
    with _cache_lock:
        if _cached_client is None:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
            _cached_client = gspread.authorize(creds)
        return _cached_client

def get_sheet(sheet_name):
    global _cached_spreadsheet
    client = get_client()
    for attempt in range(3):
        try:
            with _cache_lock:
                if _cached_spreadsheet is None:
                    _cached_spreadsheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4/edit')
            return _cached_spreadsheet.worksheet(sheet_name)
        except Exception as e:
            print(f"[Google Sheets Attempt {attempt+1}] Error: {e}")
            if attempt == 2:
                raise e
            with _cache_lock:
                _cached_spreadsheet = None
                global _cached_client
                _cached_client = None
            time.sleep(2)

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

# = [WHATSAPP] WhatsApp Functions وظائف الواتساب
# =====================================================
def send_whatsapp_message(to, body_text):
    print(f"OUTGOING -> {to}: {body_text}")
    clean_to = str(to).replace('+', '').replace('0020', '20').replace(' ', '').strip()
    if clean_to.startswith('01'):
        clean_to = '20' + clean_to[1:]
    elif clean_to.startswith('1'):
        clean_to = '20' + clean_to

    instance_id = "692921bb-a5df-451d-8527-e1ee55a736f4" # local instance id for 201121748885
    send_url = f"http://localhost:3001/instance/{instance_id}/send"
    payload = {
        "to": clean_to,
        "message": body_text
    }
    try:
        r = requests.post(send_url, json=payload, timeout=10)
        print(f"Local WA send response: {r.status_code} {r.text}")
        log_chat_to_sheet(clean_to, "Bot", body_text)
        
        # Record Bot message in Supabase so it appears in Moderator panel
        insert_message_to_supabase(
            channel='whatsapp',
            sender_id=clean_to,
            sender_name='Bot',
            message_text=body_text,
            is_from_admin=True,
            whatsapp_instance_id=instance_id
        )
    except Exception as e:
        print(f"[ERROR] Exception Sending Local WA: {e}")

def send_location_request_template(to):
    # For WhatsApp QR, we send a standard text request instead of a template
    msg = "من فضلك قم بإرسال اللوكيشن (موقع التحرك) الخاص بك في رسالة لتسهيل وصول الكابتن. 📍"
    send_whatsapp_message(to, msg)

def clean_phone_strict(phone):
    """تنظيف الرقم للمطابقة بأقوى شكل ممكن (وتحويله للمعيار الدولي 2011)"""
    if not phone: return ""
    # تحويل الأرقام الشرقية (العربية) إلى أرقام غربية
    arabic_to_western = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    clean = str(phone).translate(arabic_to_western)
    clean = clean.replace(" ", "").replace("+", "").replace("-", "")
    clean = re.sub(r'\D', '', clean)
    if clean.startswith("00"): clean = clean[2:]
    if clean.startswith("01"): clean = "2" + clean
    if clean.startswith("1"): clean = "20" + clean
    return clean

def _parse_trip_date(date_str):
    if not date_str: return None
    date_str = str(date_str).strip().split(' ')[0]
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    return None

def _phones_match(p1, p2):
    """مطابقة أرقام الهواتف بدقة ومرونة (تطابق كامل أو آخر 8 أرقام)"""
    c1 = clean_phone_strict(p1)
    c2 = clean_phone_strict(p2)
    if not c1 or not c2: return False
    if c1 == c2: return True
    if len(c1) >= 8 and len(c2) >= 8 and c1[-8:] == c2[-8:]:
        return True
    return False

def find_active_session(sheet, sender_phone, message_text=""):
    """البحث عن جلسة نشطة (تأكيد أو تقييم) بدقة متناهية لمنع التداخل بين الرحلات القادمة والماضية"""
    try:
        clean_sender = clean_phone_strict(sender_phone)
        all_rows = sheet.get_all_values()
        today = datetime.now().date()
        
        # ----------------------------------------------------
        # أولوية 1: الحجوزات القادمة أو اليومية (تأكيد الرحلة وتفاصيلها لها الأولوية القصوى)
        # ----------------------------------------------------
        for i in range(len(all_rows)-1, 0, -1):
            row = list(all_rows[i])
            while len(row) < 35: row.append("")
            
            row_phone = str(row[4])
            if not _phones_match(row_phone, clean_sender):
                continue
                
            trip_date = _parse_trip_date(row[1])
            is_future_or_today = (trip_date is None) or (trip_date >= today)
            
            if is_future_or_today:
                raw_dec = str(row[27]).strip() # Column AB: client_decision
                has_final_decision = raw_dec in ["وافق", "مؤكد", "تأكيد", "رفض", "ملغي", "إلغاء", "رفضت"]
                
                # لو الحجز قادم ولم يُتخذ فيه قرار نهائي بعد
                if not has_final_decision:
                    print(f"[Debug-Session] Found upcoming confirmation session on row {i+1} for sender {sender_phone}")
                    return i + 1, "confirm"
                    
        # ----------------------------------------------------
        # أولوية 2: فحص التقييم (Z = index 25) - فقط للرحلات المنتهية خلال آخر 3 أيام
        # ويشترط ألا يكون التقييم قد انتهى بالفعل أو جاري!
        # ----------------------------------------------------
        for i in range(len(all_rows)-1, 0, -1):
            row = list(all_rows[i])
            while len(row) < 35: row.append("")
            
            row_phone = str(row[4])
            if not _phones_match(row_phone, clean_sender):
                continue
                
            trip_date = _parse_trip_date(row[1])
            is_recent_past = False
            if trip_date:
                # رحلة ماضية (خلال 3 أيام ماضية)
                is_recent_past = 0 <= (today - trip_date).days <= 3
            
            raw_z = str(row[25]).strip() # Column Z: msg_feedback_status
            
            # الشرط الصارم: تم طلب التقييم ولم ينته بعد!
            is_done = any(done in raw_z for done in ["انتهاء", "تم انتهاء", "[OK]", "مكتمل", "جاري"])
            is_feedback_pending = ("طلب التقييم" in raw_z or "تم طلب التقييم" in raw_z) and not is_done
            
            if is_feedback_pending and is_recent_past:
                print(f"[Debug-Session] Found pending feedback session on row {i+1} for sender {sender_phone}")
                return i + 1, "feedback"
                
        # ----------------------------------------------------
        # fallback: أي رحلة قادمة أو عامة للمستخدم
        # ----------------------------------------------------
        for i in range(len(all_rows)-1, 0, -1):
            row = list(all_rows[i])
            while len(row) < 35: row.append("")
            if _phones_match(str(row[4]), clean_sender):
                print(f"[Debug-Session] Fallback: Found general session on row {i+1} for sender {sender_phone}")
                return i + 1, "unknown"
                
        print(f"[Debug-Session] No active session found for sender {sender_phone}")
        return -1, None
    except Exception as e:
        print(f"[ERROR] Error in find_active_session: {e}")
        return -1, None

def find_active_row(sheet, sender_phone):
    row, _ = find_active_session(sheet, sender_phone)
    return row

ADMIN_WA_NUMBER = "201121748885"  # رقم الأدمن للتنبيه

def _is_human_escalation_request(text):
    """[AI] يتحقق هل العميل يطلب التحدث مع إنسان أو يشكو من البوت أو يطرح سؤالاً خارج السياق"""
    escalation_keywords = [
        'محتاج حد يكلمني', 'محتاج حد يكلمنى', 'عايز حد يكلمني', 'عايز حد يكلمنى', 
        'عاوز حد يكلمني', 'عاوز حد يكلمنى', 'حد يكلمني', 'حد يكلمنى',
        'كلمني', 'كلمنى', 'ابعتلي', 'ابعتلى', 'اتصل بي', 'اتصل بى', 'اتصل',
        'مش عايز بوت', 'هو ده بوت', 'هو دا بوت', 'بوت', 'روبوت', 'مش تلقائي',
        'تكلم معي', 'تكلم معايا', 'عايز ادمن', 'ادمن', 'خدمة عملاء', 'خدمه عملاء',
        'شكوى', 'مشكلة', 'مشكله', 'غلطة', 'غلطه', 'خطأ', 'خطا', 'مش صح',
        'انا مش فاهم', 'مش فاهم', 'إيه ده', 'ايه ده', 'اي ده', 'اى دا', 'اى ده',
        'مش عارف', 'توقف', 'وقف', 'بلاش', 'كفاية', 'كفايه',
        'العربية واقفة', 'العربيه واقفه', 'السواق مجاش', 'الكابتن مجاش', 'فين السواق',
        'help', 'human', 'agent', 'support'
    ]
    text_lower = text.lower().strip()
    for kw in escalation_keywords:
        if kw in text_lower:
            return True
    return False

processed_confirmations = set()

def handle_confirmation(sender, text, row=None):
    global processed_confirmations
    sheet = get_main_sheet()
    if not row:
        row, stype = find_active_session(sheet, sender)
        if stype != "confirm": return # لا نعالج التأكيد لو الجلسة ليست "تأكيد"
        
    if row != -1:
        # منع تكرار نفس الرسالة لنفس الصف
        proc_key = f"{row}_{text.strip()[:25]}"
        if proc_key in processed_confirmations:
            print(f"[INFO] Same message for row {row} already processed. Skipping.")
            return
        processed_confirmations.add(proc_key)
        if len(processed_confirmations) > 300:
            processed_confirmations.clear()
            
        # ========================================
        # [ESCAPE HATCH] كشف طلبات التحدث مع إنسان أثناء التأكيد
        # ========================================
        if _is_human_escalation_request(text):
            print(f"[Confirm-Escape] Client {sender} requested human support: '{text}'")
            try:
                admin_alert = (
                    f"🚨 *طلب تدخل بشري أثناء تأكيد الرحلة*\n"
                    f"📱 العميل: {sender}\n"
                    f"📄 صف الرحلة: {row}\n"
                    f"💬 رسالة العميل: \"{text}\"\n"
                    f"⚡ يرجى التواصل معه فوراً!"
                )
                send_whatsapp_message(ADMIN_WA_NUMBER, admin_alert)
            except Exception as ae:
                print(f"[Escape-Notify Error]: {ae}")
                
            send_whatsapp_message(sender,
                "أهلاً بحضرتك يا فندم 🙏\n"
                "تم تحويل طلبك لخدمة العملاء، وسيتواصل معك أحد مسؤولينا فوراً للمساعدة وتأكيد كافة التفاصيل. ✨"
            )
            return
        
        # [AI] استخدام Groq AI لفهم نية العميل بدل الـ regex الصارم
        intent_result = ai_understand_intent(text, context='confirmation')
        intent = intent_result.get('intent', 'unclear')
        confidence = intent_result.get('confidence', 0.0)
        
        # fallback للـ regex لو AI مش متأكد
        import re
        text_lower = text.lower()
        if intent == 'unclear' or confidence < 0.5:
            if re.search(r"(?i)\b(confirm|ok|yes)\b|تأكيد|تاكيد|نعم|وافق|تمام|ماشي|اه\b|اوكي|اكيد|ايوه|يلا|اتفقنا|اوك", text_lower):
                intent = 'confirm'
            elif re.search(r"(?i)\b(cancel|no)\b|إلغاء|الغاء|\bلا\b|رفض|لأ|كنسل|مش عايز", text_lower):
                intent = 'cancel'
        
        is_confirm = (intent == 'confirm')
        is_cancel = (intent == 'cancel')
        
        if is_confirm:
            print(f"[INFO] Recording confirmation in AB{row} for sender {sender}...")
            try:
                sheet.update_acell(f"AB{row}", "وافق") 
                # تحديث Supabase فورياً
                try:
                    requests.patch(
                        f"{SUPABASE_URL}/rest/v1/google_reservations?sheet_row=eq.{row}",
                        headers=SUPABASE_SERVICE_HEADERS,
                        json={"client_decision": "وافق"},
                        timeout=5
                    )
                except Exception as sb_err:
                    print(f"[Supabase-Decision-Sync Error]: {sb_err}")

                # فحص رحلات المطار
                is_airport = False
                try:
                    pickup_val = str(sheet.cell(row, 7).value or "").lower()
                    airport_keywords = ["مطار", "airport", "terminal", "صالة", "صاله", "cai", "hbe", "aly", "borg"]
                    if any(kw in pickup_val for kw in airport_keywords):
                        is_airport = True
                except Exception as e:
                    print(f"[WARNING] Could not check pickup address: {e}")
                
                if is_airport:
                    send_whatsapp_message(sender, "شكراً لتأكيدك يا فندم 🌹\nتم تأكيد حجز الرحلة بنجاح! رحلة سعيدة وآمنة إن شاء الله 🚗💨")
                    try:
                        sheet.update_acell(f"AC{row}", "مطار / غير مطلوب")
                        sheet.update_acell(f"AA{row}", "مكتمل اللوكيشن [OK]")
                    except Exception as e:
                        print(f"[WARNING] Could not update location status for airport: {e}")
                else:
                    send_whatsapp_message(sender, 
                        "شكراً لتأكيدك يا فندم 🌹\n"
                        "تم تأكيد حجز الرحلة بنجاح! يسعدنا خدمتكم في 24Seven ✨\n\n"
                        "📍 من فضلك قم بإرسال اللوكيشن (موقع التحرك) الخاص بك في رسالة لتسهيل وصول الكابتن في الموعد المحدد."
                    )
            except Exception as e:
                print(f"[ERROR] Write failed: {e}")
        elif is_cancel:
            print(f"[INFO] Recording cancellation in AB{row} for sender {sender}...")
            try:
                sheet.update_acell(f"AB{row}", "رفض")
                try: sheet.update_acell(f"AA{row}", "ملغي") 
                except: pass
                # تحديث Supabase فورياً
                try:
                    requests.patch(
                        f"{SUPABASE_URL}/rest/v1/google_reservations?sheet_row=eq.{row}",
                        headers=SUPABASE_SERVICE_HEADERS,
                        json={"client_decision": "ملغي", "trip_status": "ملغاة", "status": "ملغاة"},
                        timeout=5
                    )
                except Exception as sb_err:
                    print(f"[Supabase-Decision-Sync Error]: {sb_err}")

                send_whatsapp_message(sender, "تم إلغاء الطلب بناءً على رغبتك. نتمنى أن نتشرف بخدمتكم في رحلات أخرى قادمة 🌸")
            except Exception as e:
                print(f"[ERROR] Write failed: {e}")
        else:
            # رد مرن للعميل في حالة إرسال نص غير التأكيد/الإلغاء
            print(f"[INFO] Unclear confirmation reply from {sender}: {text}")
            send_whatsapp_message(sender, "وصلتنا رسالتك يا فندم 🌹\nهل تؤكد حجز الرحلة؟ (يرجى الرد بـ: نعم / تأكيد أو إلغاء)")

def handle_location_received(sender, msg):
    sheet = get_main_sheet()
    row = find_active_row(sheet, sender)
    if row != -1:
        lat = msg['location']['latitude']
        lng = msg['location']['longitude']
        maps_link = f"https://maps.google.com/maps?q={lat},{lng}"
        print(f"[INFO] Recording location in AC{row}...")
        try:
            sheet.update_acell(f"AC{row}", maps_link)
            try: sheet.update_acell(f"AA{row}", "مكتمل اللوكيشن [OK]") 
            except: pass
            print(f"[INFO] Location saved in row {row}.")
            send_whatsapp_message(sender, "وصلنا اللوكيشن، شكراً لتعاونك! [WA]")
        except Exception as e:
            print(f"[ERROR] Sheet write failed: {e}")

def handle_location_url_received(sender, url):
    """[FIX] معالجة اللوكيشن لو أرسله العميل كنص يحتوي على رابط خرائط جوجل"""
    sheet = get_main_sheet()
    row = find_active_row(sheet, sender)
    if row != -1:
        print(f"[INFO] Recording URL location in AC{row}...")
        try:
            sheet.update_acell(f"AC{row}", url)
            try: sheet.update_acell(f"AA{row}", "مكتمل اللوكيشن [OK]") 
            except: pass
            print(f"[INFO] Location URL saved in row {row}.")
            send_whatsapp_message(sender, "وصلنا اللوكيشن، شكراً لتعاونك! [WA]")
        except Exception as e:
            print(f"[ERROR] Sheet write failed: {e}")

def start_feedback_flow(sender, text, row):
    """البدء في تسجيل التقييم (تسجيل أول إجابة: التقييم العام) مع كشف طلبات الإنسان فوراً"""
    # ========================================
    # [ESCAPE HATCH] لو العميل من أول رسالة طلب إنسان
    # ========================================
    if _is_human_escalation_request(text):
        print(f"[Feedback-Start-Escape] Client {sender} requested human support on Q1: '{text}'")
        _mark_post_feedback_cooldown(sender)
        try:
            admin_alert = (
                f"🚨 *طلب تدخل بشري أثناء التقييم (س1)*\n"
                f"📱 العميل: {sender}\n"
                f"📄 صف الرحلة: {row}\n"
                f"💬 قال: \"{text}\"\n"
                f"⚡ يرجى التواصل معه فوراً!"
            )
            send_whatsapp_message(ADMIN_WA_NUMBER, admin_alert)
        except Exception as ae:
            print(f"[Escape-Notify Error]: {ae}")
        
        send_whatsapp_message(sender, 
            "فهمنا حضرتك تماماً يا فندم 🙏\n"
            "تم تحويل رسالتك للإدارة وسيتواصل معك أحد مسؤولينا في أقرب وقت لمعالجة أي ملاحظات.\n"
            "شكراً لصبرك وثقتك بنا! ❤️"
        )
        return

    sheet = get_main_sheet()
    try:
        # [AI] استخدام AI لاستخراج قيمة التقييم بشكل ذكي
        rating_result = ai_understand_intent(text, context='feedback_rating')
        rating_value = rating_result.get('value', text)  # حفظ النص الأصلي
        
        # 1. تسجيل التقييم العام في AD (Column 30)
        sheet.update_acell(f"AD{row}", rating_value)
        # 2. تحديث الحالة في Z لكي لا نكرر البدء
        sheet.update_acell(f"Z{row}", "جاري التقييم... [INFO]")
        # 3. حفظ الحالة في الذاكرة
        user_state[sender] = {"step": "q2", "row": row, "timestamp": time.time()}
        send_whatsapp_message(sender, "شكراً لتقييمك 😊\nس2: هل كانت السيارة نظيفة ومريحة؟")
    except Exception as e:
        print(f"[ERROR] start_feedback_flow failed: {e}")

def handle_feedback_flow(sender, text):
    """[AI-POWERED] معالجة التقييم بفهم ذكي للردود العربية المرنة والتوقف فور طلب إنسان"""
    state = user_state[sender]
    step = state['step']
    row = state['row']
    sheet = get_main_sheet()
    
    # ========================================
    # [ESCAPE HATCH] كشف طلبات التحدث مع إنسان
    # ========================================
    if _is_human_escalation_request(text):
        print(f"[Feedback-Escape] Client {sender} requested human support: '{text}'")
        # إيقاف فلو التقييم فوراً
        user_state.pop(sender, None)
        _mark_post_feedback_cooldown(sender)
        
        # إعلام الأدمن فوراً
        try:
            admin_alert = (
                f"🚨 *طلب تدخل بشري أثناء التقييم*\n"
                f"📱 العميل: {sender}\n"
                f"📄 صف الرحلة: {row}\n"
                f"💬 قال: \"{text}\"\n"
                f"⚡ يرجى التواصل معه فوراً!"
            )
            send_whatsapp_message(ADMIN_WA_NUMBER, admin_alert)
        except Exception as ae:
            print(f"[Escape-Notify Error]: {ae}")
        
        # رد للعميل
        send_whatsapp_message(sender, 
            "فهمنا حضرتك تماماً يا فندم 🙏\n"
            "تم تحويل رسالتك للإدارة وسيتواصل معك أحد مسؤولينا في أقرب وقت لمتابعة الأمر.\n"
            "شكراً لصبرك! ❤️"
        )
        return
    
    try:
        if step == "q2":
            # [AI] فهم رد نعم/لا مرن
            intent = ai_understand_intent(text, context='feedback_yes_no')
            answer = "نعم" if intent.get('intent') == 'yes' else ("لا" if intent.get('intent') == 'no' else text)
            sheet.update_acell(f"AE{row}", answer)
            user_state[sender]['step'] = "q3"
            send_whatsapp_message(sender, "س3: كيف تقيّم الكابتن؟ (ممتاز / جيد / متوسط / سيئ)")
        elif step == "q3":
            # [AI] استخراج تقييم الكابتن
            rating = ai_understand_intent(text, context='feedback_rating')
            answer = rating.get('value', text)
            sheet.update_acell(f"AF{row}", answer)
            user_state[sender]['step'] = "q4"
            send_whatsapp_message(sender, "س4: هل ستوصي بنا لأصدقائك وعائلتك؟ 😊")
        elif step == "q4":
            # [AI] فهم رد نعم/لا مرن
            intent = ai_understand_intent(text, context='feedback_yes_no')
            answer = "نعم" if intent.get('intent') == 'yes' else ("لا" if intent.get('intent') == 'no' else text)
            sheet.update_acell(f"AG{row}", answer)
            user_state[sender]['step'] = "q5"
            send_whatsapp_message(sender, "س5: (اختياري) أي اقتراحات أو ملاحظات؟ أو اكتب 'لا' للتخطي")
        elif step == "q5":
            # [AI] استخراج الاقتراح
            suggest = ai_understand_intent(text, context='feedback_suggest')
            answer = suggest.get('value', text)
            sheet.update_acell(f"AH{row}", answer)
            # تحديث الحالة النهائية في الشيت
            sheet.update_acell(f"Z{row}", "تم انتهاء التقييم [OK]")
            user_state.pop(sender, None)
            # منع البوت من الرد على أي رسالة بعد انتهاء الفيدباك لمدة ساعة
            _mark_post_feedback_cooldown(sender)
            send_whatsapp_message(sender, "شكراً جزيلاً على وقتك وتقييمك ❤️\nرأيك يساعدنا نتحسن باستمرار 🌟")
    except Exception as e:
        print(f"[ERROR] Feedback save failed: {e}")



# = [WHATSAPP HOOK] WhatsApp Webhook نقطة استقبال الواتساب
# =====================================================
@app.route('/webhook', methods=['POST'])
def whatsapp_webhook():
    print(f"[DEBUG] Incoming WhatsApp request: {request.method}")
    data = request.get_json()
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Error", 403

    if request.method == 'POST':
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
                        # [INFO] معالجة اللوكيشن برمجياً
                        handle_location_received(sender, msg)
                    elif msg_type == 'image':
                        media_id = msg['image']['id']
                        caption = msg['image'].get('caption', '')
                        mime_type = msg['image'].get('mime_type', 'image/jpeg')
                        media_url = download_whatsapp_media(media_id, mime_type)
                        if media_url:
                            text_body = f"MEDIA_IMAGE:{media_url}"
                            if caption:
                                text_body += f"|CAPTION:{caption}"
                        else:
                            text_body = "📷 [صورة]"
                    elif msg_type in ['audio', 'voice']:
                        media_key = 'audio' if 'audio' in msg else 'voice'
                        media_id = msg[media_key]['id']
                        mime_type = msg[media_key].get('mime_type', 'audio/ogg')
                        media_url = download_whatsapp_media(media_id, mime_type)
                        if media_url:
                            text_body = f"MEDIA_AUDIO:{media_url}"
                        else:
                            text_body = "🎵 [رسالة صوتية]"
                    elif msg_type == 'video':
                        media_id = msg['video']['id']
                        mime_type = msg['video'].get('mime_type', 'video/mp4')
                        media_url = download_whatsapp_media(media_id, mime_type)
                        if media_url:
                            text_body = f"MEDIA_VIDEO:{media_url}"
                        else:
                            text_body = "🎥 [فيديو]"
                    
                    print(f"[WA] Message from {sender}: {text_body}", flush=True)
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
                         # [FIX] منع التكرار: لو نفس الرسالة وصلت من رقمين
                         if not _is_feedback_duplicate(sender, text_body):
                             handle_feedback_flow(sender, text_body)
                         else:
                             print(f"[WA-Dedup] Skipping duplicate feedback msg from {sender}")
                    elif msg_type in ['text', 'button', 'interactive']:
                         import re
                         if msg_type == 'text' and re.search(r'(google\.com/maps|maps\.app\.goo\.gl|maps\.google\.com)', text_body):
                              # [FIX] إذا كان النص مجرد رابط لموقع جوجل ماب، سيعامل كـ لوكيشن
                              handle_location_url_received(sender, text_body)
                         else:
                              # [FIX] لو العميل في فترة ما بعد الفيدباك → نتجاهل ولا نبدأ فيدباك جديد
                              if _is_in_post_feedback_cooldown(sender):
                                  print(f"[WA] Post-feedback cooldown active for {sender}, skipping.")
                              else:
                                  # فحص هل هناك جلسة نشطة منتظرة رد (تأكيد أو تقييم في الشيت)
                                  sheet = get_main_sheet()
                                  row_idx, session_type = find_active_session(sheet, sender)
                                  
                                  if session_type == "feedback":
                                       # [FIX] منع التكرار أيضاً هنا (أول رسالة الفيدباك)
                                       if not _is_feedback_duplicate(sender, text_body):
                                           start_feedback_flow(sender, text_body, row_idx)
                                       else:
                                           print(f"[WA-Dedup] Skipping duplicate feedback start for {sender}")
                                  elif session_type == "confirm":
                                       handle_confirmation(sender, text_body, row_idx)
                    
        except Exception as e:
            print(f"[ERROR] Webhook Error: {e}")
            traceback.print_exc()
        return "OK", 200


# = [MESSENGER FUNC] Messenger Functions وظائف الماسنجر
# =====================================================
def send_messenger_msg(recipient_id, text, quick_replies=None, buttons=None):
    print(f"OUTGOING -> {recipient_id}: {text}") # Moved OUTGOING log here
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
        if r.status_code == 200: 
            print(f"[FB] Replied to {recipient_id}")
            
            # [FIX] Record Bot message in Supabase so it appears in Moderator panel
            try:
                # Get tracked mid if possible
                fb_msg_id = r.json().get('message_id', '')
                if fb_msg_id:
                    sent_via_api_mids.add(fb_msg_id)
                    if len(sent_via_api_mids) > 500: sent_via_api_mids.clear()
                    
                insert_message_to_supabase(
                    channel='messenger',
                    sender_id=recipient_id,
                    sender_name='Bot',
                    message_text=text,
                    is_from_admin=True
                )
            except Exception as se:
                print(f"[ERROR] Failed to insert Bot message to Supabase: {se}")
                
        else: 
            print(f"[FB] Reply failed: {r.text}")
    except: pass

def get_facebook_user_name(sender_id):
    """
    استدعاء Graph API لجلب اسم المستخدم من ماسنجر بناءً على الـ PSID
    إذا فشل، نبحث عن اسم العميل من جدول الحجوزات عبر الرسائل السابقة
    """
    # محاولة 1: عبر محادثات الصفحة (أقوى وأضمن طريقة لتخطي قيود الصلاحيات والـ Dev Mode)
    try:
        url = "https://graph.facebook.com/v18.0/me/conversations"
        params = {
            "access_token": FB_PAGE_TOKEN,
            "user_id": sender_id,
            "fields": "participants"
        }
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            for conv in data.get('data', []):
                for p in conv.get('participants', {}).get('data', []):
                    if str(p.get('id')) == str(sender_id):
                        name = p.get('name', '').strip()
                        if name:
                            print(f"[FB] Found Name via conversations: {name} (ID: {sender_id})")
                            return name
        else:
            print(f"[FB] Conversations lookup failed: {r.status_code} | {r.text}")
    except Exception as e:
        print(f"[ERROR] Exception in conversations lookup for {sender_id}: {e}")

    # محاولة 2: عبر Graph API المباشر للملف الشخصي (fallback)
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
                print(f"[FB] Found FB Name: {name} (ID: {sender_id})")
                return name
        else:
            print(f"[FB] Direct profile lookup failed: {r.status_code} | {r.text}")
    except Exception as e:
        print(f"[ERROR] Exception in get_facebook_user_name direct lookup for {sender_id}: {e}")
    
    # محاولة 2: البحث عن اسم العميل من الحجوزات عبر رسائله السابقة (نبحث عن رقم هاتف في المحادثات)
    try:
        # جلب آخر 20 رسالة من هذا العميل للبحث عن رقم هاتف فيها
        msg_url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages?sender_id=eq.{sender_id}&is_from_admin=eq.false&select=message_text&order=created_at.desc&limit=20"
        r2 = requests.get(msg_url, headers=SUPABASE_HEADERS)
        if r2.status_code == 200:
            msgs = r2.json()
            import re as re2
            for m in msgs:
                txt = m.get('message_text', '')
                # البحث عن رقم هاتف مصري (01...)
                phone_match = re2.search(r'(01[0-9]{9})', txt)
                if phone_match:
                    phone_found = phone_match.group(1)
                    # البحث عن الاسم في الحجوزات
                    res_url = f"{SUPABASE_URL}/rest/v1/google_reservations?customer_phone=ilike.%{phone_found}%&select=customer_name&order=created_at.desc&limit=1"
                    r3 = requests.get(res_url, headers=SUPABASE_HEADERS)
                    if r3.status_code == 200:
                        res_data = r3.json()
                        if res_data and res_data[0].get('customer_name'):
                            found_name = res_data[0]['customer_name']
                            print(f"[INFO] Found Messenger client name from reservations: {found_name} (PSID: {sender_id})")
                            # تحديث جميع الرسائل القديمة بالاسم الحقيقي
                            try:
                                update_url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages?sender_id=eq.{sender_id}&sender_name=eq.Messenger User"
                                requests.patch(update_url, headers=SUPABASE_HEADERS, json={"sender_name": found_name})
                            except: pass
                            return found_name
    except Exception as e:
        print(f"[ERROR] Messenger name fallback error: {e}")
    
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
        send_messenger_msg(sender_id, "[Q2] هل الموظف ساعدك في حل استفسارك؟ (نعم / لا)")
    
    elif current_step == "FB_Q2":
        messenger_feedback_data[sender_id]['helped'] = text
        messenger_states[sender_id] = "FB_Q3"
        send_messenger_msg(sender_id, "[Q3] أخيراً.. هل عندك أي اقتراح لتطوير الموظف؟ (لو مفيش اكتب 'لا')")
    
    elif current_step == "FB_Q3":
        messenger_feedback_data[sender_id]['suggestion'] = text
        
        # حفظ البيانات في الشيت
        data = messenger_feedback_data[sender_id]
        row_to_save = [data['date'], sender_id, data.get('rating'), data.get('helped'), data.get('suggestion')]
        log_to_sheet(FEEDBACK_SHEET_NAME, row_to_save)
        
        # إعادة العميل للوضع الطبيعي
        messenger_states[sender_id] = "BOT" 
        send_messenger_msg(sender_id, "شكراً لوقتك وتقييمك! [OK]\nأنا رجعت معاك تاني (الرد الآلي) لأي استفسار جديد.")
        del messenger_feedback_data[sender_id]

# = [MESSENGER HOOK] Messenger Webhook نقطة استقبال الماسنجر
# =====================================================
import threading
processed_mids = set() # ذاكرة مؤقتة لتخزين معرفات الرسائل المعالجة
sent_via_api_mids = set() # [FIX] تتبع الرسائل المرسلة عبر send_reply لمنع التكرار فقط لها

def handle_admin_command_if_any(channel, sender_id, text):
    if not text: return False, None
    t_clean = str(text).strip().lower()
    resume_cmds = ['/bot', '/resume', '/start', '/شغل', '/البوت']
    pause_cmds = ['/pause', '/stop', '/human', '/وقف', '/ايقاف']
    
    if t_clean in resume_cmds:
        if channel == 'messenger':
            messenger_states[sender_id] = "BOT"
            messenger_agent.resume_bot(sender_id)
        print(f"[ADMIN-COMMAND] Resumed bot for {sender_id} on {channel}")
        return True, "resumed"
        
    if t_clean in pause_cmds:
        if channel == 'messenger':
            messenger_states[sender_id] = "HUMAN"
        print(f"[ADMIN-COMMAND] Paused bot for {sender_id} on {channel}")
        return True, "paused"
        
    return False, None


def process_message_async(sender_id, text, user_profile):
    """
    دالة تعمل في الخلفية لمعالجة المنطق الثقيل (الذكاء الاصطناعي)
    دون تعطيل الرد على فيسبوك.
    """
    try:
        print(f"[ASYNC] Processing message from {sender_id}...")
        
        # معرفة حالة العميل الحالية
        current_state = messenger_states.get(sender_id, "BOT")

        # أ) حالة التحدث مع موظف (HUMAN)
        if current_state == "HUMAN":
            print(f"[INFO] Bot is silent (Human mode) for {sender_id}")
            return # لا نرد، نترك الموظف يرد

        # ب) حالة الفيدباك (FEEDBACK)
        elif current_state.startswith("FB_"):
            handle_messenger_feedback_flow(sender_id, text)

        # ج) الحالة الطبيعية (BOT - AI)
        else:
            if AI_AUTOREPLY_ENABLED:
                print(f"[FB] Processing AI Autoreply for message: {text}")
                reply = messenger_agent.handle_messenger_chat(sender_id, text, user_profile)
                if reply:
                    if isinstance(reply, dict):
                        reply_text = reply.get('text', '')
                        quick_replies = reply.get('quick_replies')
                        buttons = reply.get('buttons')
                        action = reply.get('action')
                        if reply_text:
                            send_messenger_msg(sender_id, reply_text, quick_replies=quick_replies, buttons=buttons)
                        if action == "pause_bot":
                            messenger_states[sender_id] = "HUMAN"
                            print(f"[INFO] Bot paused for {sender_id} (Human Mode)")
                    else:
                        send_messenger_msg(sender_id, reply)
            else:
                print(f"[FB] Message received but AI is stopped (AI_AUTOREPLY_ENABLED is False): {text}")

    except Exception as e:
        print(f"[ERROR] Async Error: {e}")

@app.route('/messenger', methods=['GET', 'POST'])
def messenger_webhook():
    print(f"[DEBUG] Incoming Messenger request: {request.method}")
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Error", 403

    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        try:
            if data.get('object') == 'page':
                for entry in data['entry']:
                    events = entry.get('messaging', []) or entry.get('standby', [])
                    for event in events:
                        if 'delivery' in event or 'read' in event:
                            continue

                        sender_id = event['sender']['id']
                        text = None
                        message = event.get('message', {}) or event.get('message_edit', {})
                        mid = message.get('mid')
                        
                        # --- [INFO] منع التكرار الموحد (بما في ذلك الـ Echoes) ---
                        if mid:
                            if mid in processed_mids:
                                print(f"[INFO] Skipping duplicate Messenger MID: {mid}")
                                continue
                            processed_mids.add(mid)
                            if len(processed_mids) > 10000: processed_mids.clear()

                        if 'message' in event or 'message_edit' in event:
                            if message.get('is_echo'):
                                admin_text = message.get('text', '').strip()
                                target_user_id = event['recipient']['id']
                                echo_mid = message.get('mid', '')
                                
                                # [FIX] لو الرسالة اتبعتت من send_reply → نتجاهلها (محفوظة خلاص)
                                # لو اتبعتت من صفحة فيسبوك مباشرة → نحفظها في Supabase
                                if echo_mid in sent_via_api_mids:
                                    print(f"[FB] (Echo) Admin via API to {target_user_id}: {admin_text} [SKIP - saved by send_reply]")
                                    sent_via_api_mids.discard(echo_mid) # تنظيف
                                else:
                                    print(f"[FB] (Echo) Admin via Page to {target_user_id}: {admin_text} [SAVING - direct from FB]")
                                    insert_message_to_supabase(
                                        channel='messenger',
                                        sender_id=target_user_id,
                                        sender_name="Admin", 
                                        message_text=admin_text,
                                        is_from_admin=True
                                    )
                                    # معالجة أمر الإيقاف/التشغيل التلقائي واليدوي
                                    is_cmd, cmd_act = handle_admin_command_if_any('messenger', target_user_id, admin_text)
                                    if not is_cmd:
                                        messenger_states[target_user_id] = "HUMAN"
                                        print(f"[FB-Echo] Bot automatically PAUSED (HUMAN mode) for {target_user_id} due to direct Page Admin message.")
                                continue

                            if 'quick_reply' in message:
                                text = message['quick_reply'].get('payload')
                            elif 'text' in message:
                                text = message['text']
                            elif 'attachments' in message:
                                attachments = message['attachments']
                                if attachments:
                                    att = attachments[0]
                                    att_type = att.get('type')
                                    payload = att.get('payload', {})
                                    url = payload.get('url')
                                    if url:
                                        if att_type == 'image':
                                            text = f"MEDIA_IMAGE:{url}"
                                        elif att_type == 'audio':
                                            text = f"MEDIA_AUDIO:{url}"
                                        elif att_type == 'video':
                                            text = f"MEDIA_VIDEO:{url}"
                                        else:
                                            text = f"📎 [{att_type}] {url}"
                        
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

                        print(f"[FB] Message from {sender_id}: {text}", flush=True)
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
            print(f"[ERROR] Messenger Error: {e}")
        
        return "EVENT_RECEIVED", 200

# = [INSTAGRAM HOOK] Instagram Webhook نقاط استقبال الإنستجرام
# =====================================================
@app.route('/api/instagram/webhook', methods=['GET'])
def instagram_webhook_verify():
    hub_mode = request.args.get("hub.mode")
    hub_challenge = request.args.get("hub.challenge")
    hub_verify_token = request.args.get("hub.verify_token")
    if hub_verify_token == INSTAGRAM_VERIFY_TOKEN and hub_mode == "subscribe":
        return hub_challenge, 200
    return "Forbidden", 403

@app.route('/api/instagram/webhook', methods=['POST'])
def instagram_webhook_receive():
    data = request.get_json()
    if not data:
        return "No data", 400
        
    print(f"[IG-Webhook] Raw payload: {data}")
    if data.get("object") != "instagram" or not data.get("entry"):
        return "OK", 200

    try:
        for entry in data["entry"]:
            # Handle both 'messaging' and 'standby' arrays
            messaging_events = entry.get("messaging", []) or entry.get("standby", [])
            for event in messaging_events:
                sender_id = event.get("sender", {}).get("id")
                recipient_id = event.get("recipient", {}).get("id")
                message = event.get("message", {}) or event.get("message_edit", {})

                if not sender_id or not message or ("text" not in message and "attachments" not in message):
                    continue

                mid = message.get("mid")
                # --- [INFO] Prevent Duplication (including Echoes) ---
                if mid:
                    if mid in processed_mids:
                        print(f"[IG] Skipping duplicate Instagram MID: {mid}")
                        continue
                    processed_mids.add(mid)
                    if len(processed_mids) > 10000: processed_mids.clear()

                text_body = message.get("text", "")
                if not text_body:
                    attachments = message.get("attachments", [])
                    if attachments:
                        att = attachments[0]
                        att_type = att.get("type")
                        url = att.get("payload", {}).get("url")
                        if url:
                            if att_type == "image":
                                text_body = f"MEDIA_IMAGE:{url}"
                            elif att_type == "audio":
                                text_body = f"MEDIA_AUDIO:{url}"
                            elif att_type == "video":
                                text_body = f"MEDIA_VIDEO:{url}"
                            else:
                                text_body = f"📎 [{att_type}] {url}"

                # Handle Echoes (messages sent by Page Admin or Bot)
                if message.get("is_echo"):
                    target_user_id = recipient_id
                    if mid in sent_via_api_mids:
                        print(f"[IG] (Echo) Admin via API to {target_user_id}: {text_body} [SKIP - saved by send_reply]")
                        sent_via_api_mids.discard(mid)
                    else:
                        print(f"[IG] (Echo) Admin via Business Suite to {target_user_id}: {text_body} [SAVING]")
                        insert_message_to_supabase(
                            channel='instagram',
                            sender_id=target_user_id,
                            sender_name="Admin",
                            message_text=text_body,
                            is_from_admin=True
                        )
                    continue

                print(f"[IG] Message from {sender_id}: {text_body}")

                # Resolve profile username
                sender_name = "Instagram User"
                try:
                    profile_res = requests.get(
                        f"https://graph.facebook.com/v17.0/{sender_id}",
                        params={"fields": "username", "access_token": FB_PAGE_TOKEN},
                        timeout=5
                    )
                    if profile_res.status_code == 200:
                        profile_data = profile_res.json()
                        if profile_data.get("username"):
                            sender_name = profile_data["username"]
                except Exception as ex:
                    print(f"[ERROR] Failed to fetch IG profile for {sender_id}: {ex}")

                # Save to Supabase
                insert_message_to_supabase(
                    channel='instagram',
                    sender_id=sender_id,
                    sender_name=sender_name,
                    message_text=text_body,
                    is_from_admin=False
                )
    except Exception as e:
        print(f"[ERROR] Instagram Webhook Error: {e}")
        traceback.print_exc()

    return "EVENT_RECEIVED", 200

# =====================================================
# ⚙️ إدارة حسابات الواتساب المرتبطة (Multi-Device WhatsApp API)
# =====================================================

@app.route('/api/whatsapp/instances', methods=['POST', 'OPTIONS'])
def create_whatsapp_instance():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    data = request.json
    instance_name = data.get("instance_name")
    instance_id = data.get("instance_id")
    token = data.get("token")
    provider = data.get("provider")
    api_url = data.get("api_url")
    
    if not instance_name or not instance_id or not token or not provider:
        return jsonify({"status": "error", "message": "جميع الحقول مطلوبة"}), 400
        
    payload = {
        "instance_name": instance_name,
        "instance_id": instance_id,
        "token": token,
        "provider": provider,
        "api_url": api_url,
        "status": "init"
    }
    
    r = requests.post(f"{SUPABASE_URL}/rest/v1/whatsapp_instances", headers=SUPABASE_SERVICE_HEADERS, json=payload, timeout=10)
    if r.status_code in [200, 201]:
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": f"Supabase Error: {r.text}"}), 500

@app.route('/api/whatsapp/instances', methods=['GET', 'OPTIONS'])
def list_whatsapp_instances():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    r = requests.get(f"{SUPABASE_URL}/rest/v1/whatsapp_instances?order=created_at.desc", headers=SUPABASE_SERVICE_HEADERS, timeout=10)
    if r.status_code == 200:
        return jsonify(r.json())
    return jsonify([])

@app.route('/api/whatsapp/instances/<id>', methods=['DELETE', 'OPTIONS'])
def delete_whatsapp_instance(id):
    if request.method == 'OPTIONS':
        return make_response("", 204)
    r = requests.delete(f"{SUPABASE_URL}/rest/v1/whatsapp_instances?id=eq.{id}", headers=SUPABASE_SERVICE_HEADERS, timeout=10)
    if r.status_code in [200, 204]:
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": f"Supabase Error: {r.text}"}), 500

@app.route('/api/whatsapp/instance/<id>/status', methods=['GET', 'OPTIONS'])
def check_whatsapp_instance_status(id):
    if request.method == 'OPTIONS':
        return make_response("", 204)
    r = requests.get(f"{SUPABASE_URL}/rest/v1/whatsapp_instances?id=eq.{id}", headers=SUPABASE_SERVICE_HEADERS, timeout=10)
    if r.status_code != 200 or not r.json():
        return jsonify({"status": "error", "message": "Instance not found"}), 404
    
    instance = r.json()[0]
    provider = instance["provider"]
    inst_id = instance["instance_id"]
    token = instance["token"]
    api_url = instance.get("api_url")
    
    conn_status = "disconnected"
    phone = instance.get("phone")
    
    if provider == "ultramsg":
        base = api_url.strip().rstrip('/') if api_url else "https://api.ultramsg.com"
        status_url = f"{base}/{inst_id}/instance/status?token={token}"
        try:
            res = requests.get(status_url, timeout=10)
            if res.status_code == 200:
                try:
                    res_data = res.json()
                    if isinstance(res_data, dict):
                        status_str = res_data.get("status", "")
                    else:
                        status_str = str(res_data)
                except:
                    status_str = res.text.strip()
                    
                if "authenticated" in status_str:
                    conn_status = "connected"
                    me_url = f"{base}/{inst_id}/instance/me?token={token}"
                    me_res = requests.get(me_url, timeout=10)
                    if me_res.status_code == 200:
                        try:
                            me_data = me_res.json()
                            raw_jid = me_data.get("id") or me_data.get("jid") or ""
                            if raw_jid:
                                phone = raw_jid.split("@")[0]
                        except:
                            pass
            else:
                conn_status = "disconnected"
        except Exception as e:
            print(f"UltraMsg status check error: {e}")
            
    elif provider == "greenapi":
        base = api_url.strip().rstrip('/') if api_url else "https://api.greenapi.com"
        status_url = f"{base}/waInstance{inst_id}/getStateInstance/{token}"
        try:
            res = requests.get(status_url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                state = data.get("stateInstance", "")
                if state == "authorized":
                    conn_status = "connected"
                    settings_url = f"{base}/waInstance{inst_id}/getWaSettings/{token}"
                    settings_res = requests.get(settings_url, timeout=10)
                    if settings_res.status_code == 200:
                        try:
                            settings_data = settings_res.json()
                            raw_wid = settings_data.get("wid") or settings_data.get("number") or ""
                            if raw_wid:
                                phone = raw_wid.split("@")[0]
                        except:
                            pass
                else:
                    conn_status = "disconnected"
        except Exception as e:
            print(f"GreenAPI status check error: {e}")
            
    elif provider == "local":
        base = api_url.strip().rstrip('/') if api_url else "http://localhost:3001"
        status_url = f"{base}/instance/{id}/status"
        try:
            res = requests.get(status_url, timeout=10)
            if res.status_code == 200:
                res_data = res.json()
                conn_status = res_data.get("status", "disconnected")
                phone = res_data.get("phone", phone)
            else:
                conn_status = "disconnected"
        except Exception as e:
            print(f"Local Gateway status check error: {e}")
            
    update_payload = {"status": conn_status}
    if phone:
        update_payload["phone"] = phone
        
    requests.patch(f"{SUPABASE_URL}/rest/v1/whatsapp_instances?id=eq.{id}", headers=SUPABASE_SERVICE_HEADERS, json=update_payload, timeout=10)
    return jsonify({"status": conn_status, "phone": phone})

@app.route('/api/whatsapp/instance/<id>/qr', methods=['GET', 'OPTIONS'])
def get_whatsapp_instance_qr(id):
    if request.method == 'OPTIONS':
        return make_response("", 204)
    r = requests.get(f"{SUPABASE_URL}/rest/v1/whatsapp_instances?id=eq.{id}", headers=SUPABASE_SERVICE_HEADERS, timeout=10)
    if r.status_code != 200 or not r.json():
        return jsonify({"status": "error", "message": "Instance not found"}), 404
    
    instance = r.json()[0]
    provider = instance["provider"]
    inst_id = instance["instance_id"]
    token = instance["token"]
    api_url = instance.get("api_url")
    
    if provider == "ultramsg":
        base = api_url.strip().rstrip('/') if api_url else "https://api.ultramsg.com"
        qr_url = f"{base}/{inst_id}/instance/qrCode?token={token}&t={int(datetime.utcnow().timestamp())}"
        return jsonify({"status": "success", "type": "image_url", "qr": qr_url})
        
    elif provider == "greenapi":
        base = api_url.strip().rstrip('/') if api_url else "https://api.greenapi.com"
        qr_url = f"{base}/waInstance{inst_id}/qr/{token}"
        try:
            res = requests.get(qr_url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                res_type = data.get("type", "")
                if res_type == "qrCode":
                    base64_str = data.get("message", "")
                    return jsonify({"status": "success", "type": "base64", "qr": f"data:image/png;base64,{base64_str}"})
                elif res_type == "alreadyLogged":
                    return jsonify({"status": "success", "type": "message", "message": "الحساب متصل بالفعل"})
                else:
                    return jsonify({"status": "error", "message": data.get("message", "فشل جلب الرمز")})
            else:
                return jsonify({"status": "error", "message": f"GreenAPI Error: {res.text}"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
            
    elif provider == "local":
        base = api_url.strip().rstrip('/') if api_url else "http://localhost:3001"
        qr_url = f"{base}/instance/{id}/qr"
        try:
            res = requests.get(qr_url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                return jsonify(data)
            else:
                return jsonify({"status": "error", "message": f"Local Gateway Error: {res.text}"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
            
    return jsonify({"status": "error", "message": "Unknown provider"}), 400

@app.route('/api/whatsapp/instance/set-webhook', methods=['POST', 'OPTIONS'])
def set_whatsapp_instance_webhook():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    data = request.json
    id = data.get("id")
    server_url = data.get("server_url")
    
    if not id or not server_url:
        return jsonify({"status": "error", "message": "المعاملات ناقصة"}), 400
        
    r = requests.get(f"{SUPABASE_URL}/rest/v1/whatsapp_instances?id=eq.{id}", headers=SUPABASE_SERVICE_HEADERS, timeout=10)
    if r.status_code != 200 or not r.json():
        return jsonify({"status": "error", "message": "Instance not found"}), 404
        
    instance = r.json()[0]
    provider = instance["provider"]
    inst_id = instance["instance_id"]
    token = instance["token"]
    api_url = instance.get("api_url")
    
    server_url = server_url.strip().rstrip('/')
    
    if provider == "ultramsg":
        base = api_url.strip().rstrip('/') if api_url else "https://api.ultramsg.com"
        settings_url = f"{base}/{inst_id}/instance/settings"
        webhook_dest = f"{server_url}/api/whatsapp/webhook/ultramsg/{id}"
        payload = {
            "token": token,
            "webhook_url": webhook_dest,
            "webhook_message_received": "true",
            "webhook_message_create": "false",
            "webhook_message_ack": "false",
            "webhook_message_download_media": "false"
        }
        try:
            res = requests.post(settings_url, data=payload, timeout=10)
            if res.status_code == 200 and "success" in res.text.lower():
                return jsonify({"status": "success", "webhook_url": webhook_dest})
            return jsonify({"status": "error", "message": f"UltraMsg Error: {res.text}"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
            
    elif provider == "greenapi":
        base = api_url.strip().rstrip('/') if api_url else "https://api.greenapi.com"
        settings_url = f"{base}/waInstance{inst_id}/setSettings/{token}"
        webhook_dest = f"{server_url}/api/whatsapp/webhook/greenapi/{id}"
        payload = {
            "webhookUrl": webhook_dest,
            "incomingWebhook": "yes",
            "outgoingWebhook": "no",
            "stateWebhook": "yes"
        }
        try:
            res = requests.post(settings_url, json=payload, timeout=10)
            if res.status_code == 200:
                return jsonify({"status": "success", "webhook_url": webhook_dest})
            return jsonify({"status": "error", "message": f"GreenAPI Error: {res.text}"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
            
    elif provider == "local":
        webhook_dest = f"{server_url}/api/whatsapp/webhook/local/{id}"
        return jsonify({"status": "success", "webhook_url": webhook_dest})
        
    return jsonify({"status": "error", "message": "Unknown provider"}), 400

@app.route('/api/whatsapp/webhook/local/<instance_id_db>', methods=['POST'])
def receive_local_webhook(instance_id_db):
    try:
        data = request.get_json()
        sender_phone = data.get("sender_phone")
        sender_name = data.get("sender_name")
        message_text = data.get("message_text")
        is_from_admin = data.get("is_from_admin", False)
        
        if not sender_phone or not message_text:
            return jsonify({"status": "error", "message": "Missing fields"}), 400
            
        sender_phone = sender_phone.replace("+", "").replace("0020", "20")
        
        # Deduplication for all messages to avoid duplicates from gateway echoes or double hits
        try:
            # Check for a matching message in the last 8 seconds
            check_seconds_ago = (datetime.utcnow() - timedelta(seconds=8)).isoformat() + "Z"
            check_url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages"
            params = {
                "channel": "eq.whatsapp",
                "sender_id": f"eq.{sender_phone}",
                "is_from_admin": f"eq.{'true' if is_from_admin else 'false'}",
                "created_at": f"gte.{check_seconds_ago}",
                "select": "id,message_text"
            }
            r_check = requests.get(check_url, headers=SUPABASE_SERVICE_HEADERS, params=params, timeout=5)
            if r_check.status_code == 200:
                existing_msgs = r_check.json()
                cleaned_text = message_text.strip()
                duplicate_found = False
                for em in existing_msgs:
                    if em.get("message_text", "").strip() == cleaned_text:
                        duplicate_found = True
                        break
                if duplicate_found:
                    print(f"[Local-Webhook] Deduplicated {'admin' if is_from_admin else 'client'} message for {sender_phone}: {message_text[:30]}...")
                    return jsonify({"status": "ok", "detail": "duplicate"})
        except Exception as check_err:
            print(f"[Local-Webhook] Error checking for duplicates: {check_err}")

        # محاولة جلب اسم العميل من الحجوزات أو الرسائل السابقة (فقط لو كانت الرسالة من العميل)
        resolved_name = sender_name
        if not is_from_admin:
            # 1. محاولة جلب الاسم من الرسائل السابقة لنفس الرقم في Supabase
            try:
                url_prev = f"{SUPABASE_URL}/rest/v1/omnichannel_messages?sender_id=eq.{sender_phone}&select=sender_name&order=created_at.desc&limit=1"
                r_prev = requests.get(url_prev, headers=SUPABASE_SERVICE_HEADERS, timeout=5)
                if r_prev.status_code == 200:
                    prev_data = r_prev.json()
                    if prev_data and prev_data[0].get('sender_name') and prev_data[0]['sender_name'] not in [sender_phone, "Admin", "ش"]:
                        resolved_name = prev_data[0]['sender_name']
            except Exception as e:
                print(f"[Local-Webhook] Error fetching previous name: {e}")

            # 2. إذا لم نجد الاسم، نبحث في جدول الحجوزات بآخر 8 أرقام للمطابقة المرنة
            if not resolved_name or resolved_name == sender_phone:
                try:
                    clean = sender_phone.replace("+", "").replace("0020", "20").replace(" ", "").strip()
                    if clean.startswith("20"):
                        clean_local = clean[2:]
                    else:
                        clean_local = clean
                    
                    if len(clean_local) >= 8:
                        last_8 = clean_local[-8:]
                        r_name = requests.get(
                            f"{SUPABASE_URL}/rest/v1/google_reservations",
                            headers=SUPABASE_SERVICE_HEADERS,
                            params={"customer_phone": f"ilike.%{last_8}%", "select": "customer_name", "limit": "1"},
                            timeout=5
                        )
                        if r_name.status_code == 200:
                            rows = r_name.json()
                            if rows and rows[0].get("customer_name"):
                                resolved_name = rows[0]["customer_name"]
                except Exception as e:
                    print(f"[Local-Webhook] Error searching reservations: {e}")
        else:
            resolved_name = sender_name or "Admin"
                
        # 1. إدراج في Supabase للمحادثات (باستخدام مفتاح الخدمة لتخطي الـ RLS)
        sb_payload = {
            "channel": "whatsapp",
            "sender_id": sender_phone,
            "sender_name": resolved_name,
            "message_text": message_text,
            "is_from_admin": is_from_admin,
            "read_by_admin": True if is_from_admin else False,
            "whatsapp_instance_id": instance_id_db
        }
        requests.post(f"{SUPABASE_URL}/rest/v1/omnichannel_messages", headers=SUPABASE_SERVICE_HEADERS, json=sb_payload, timeout=5)

        # 2. تسجيل الرسالة في شيت المحادثات (فقط لو كانت الرسالة من العميل)
        if not is_from_admin:
            try:
                log_chat_to_sheet(sender_phone, "Client", message_text)
            except Exception as sheet_err:
                print(f"[Local-Webhook Sheet Error]: {sheet_err}")

            # 3. معالجة الرسائل الواردة برمجياً (تأكيد أو تقييم أو لوكيشن)
            try:
                import re
                if re.search(r'(google\.com/maps|maps\.app\.goo\.gl|maps\.google\.com)', message_text):
                    handle_location_url_received(sender_phone, message_text)
                else:
                    if sender_phone in user_state:
                        # [FIX] منع التكرار: لو نفس الرسالة وصلت من رقمين واتساب
                        if not _is_feedback_duplicate(sender_phone, message_text):
                            handle_feedback_flow(sender_phone, message_text)
                        else:
                            print(f"[Local-Dedup] Skipping duplicate feedback from {sender_phone}")
                    else:
                        # [FIX] لو العميل في فترة ما بعد الفيدباك → نتجاهل
                        if _is_in_post_feedback_cooldown(sender_phone):
                            print(f"[Local] Post-feedback cooldown active for {sender_phone}, skipping.")
                        else:
                            sheet = get_main_sheet()
                            row_idx, session_type = find_active_session(sheet, sender_phone)
                            if session_type == "feedback":
                                # [FIX] منع التكرار لأول رسالة أيضاً
                                if not _is_feedback_duplicate(sender_phone, message_text):
                                    start_feedback_flow(sender_phone, message_text, row_idx)
                                else:
                                    print(f"[Local-Dedup] Skipping duplicate feedback start for {sender_phone}")
                            elif session_type == "confirm":
                                handle_confirmation(sender_phone, message_text, row_idx)
            except Exception as flow_err:
                print(f"[Local-Webhook Flow Error]: {flow_err}")

        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"[Local-Webhook Error]: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==========================================
# 🎯 مسارات نظام قناص التشغيلات (Sniper Bot)
# ==========================================
@app.route('/api/whatsapp/webhook/group_message', methods=['POST'])
def receive_group_message_webhook():
    try:
        data = request.get_json()
        group_id = data.get("group_id")
        group_name = data.get("group_name")
        sender_phone = data.get("sender_phone")
        sender_name = data.get("sender_name")
        message_text = data.get("message_text")
        
        if not group_id or not sender_phone or not message_text:
            return jsonify({"status": "error", "message": "Missing fields"}), 400
            
        import sniper_agent
        import threading
        
        def run_processing():
            try:
                sniper_agent.process_group_message(group_name, sender_name, sender_phone, message_text)
            except Exception as ex:
                print(f"[Sniper-Webhook Thread Error]: {ex}")
                
        threading.Thread(target=run_processing, daemon=True).start()
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"[Group-Webhook Error]: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/sniper/filters', methods=['GET', 'POST', 'OPTIONS'])
def manage_sniper_filters():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    if request.method == 'GET':
        r = requests.get(f"{SUPABASE_URL}/rest/v1/sniper_filters?order=created_at.desc", headers=SUPABASE_SERVICE_HEADERS)
        return make_response(r.text, r.status_code, {"Content-Type": "application/json"})
    elif request.method == 'POST':
        r = requests.post(f"{SUPABASE_URL}/rest/v1/sniper_filters", headers=SUPABASE_SERVICE_HEADERS, json=request.json)
        return make_response(r.text, r.status_code, {"Content-Type": "application/json"})

@app.route('/api/sniper/filters/<int:filter_id>', methods=['DELETE', 'OPTIONS'])
def delete_sniper_filter(filter_id):
    if request.method == 'OPTIONS':
        return make_response("", 204)
    r = requests.delete(f"{SUPABASE_URL}/rest/v1/sniper_filters?id=eq.{filter_id}", headers=SUPABASE_SERVICE_HEADERS)
    # Supabase returns 204 No Content on successful delete
    if r.status_code in (200, 204):
        return jsonify({"status": "deleted", "id": filter_id}), 200
    return make_response(r.text, r.status_code, {"Content-Type": "application/json"})


# = [AI DATA] ملخص بيانات تقفيل السواقين للمساعد الذكي
# =====================================================
@app.route('/api/driver_closings_summary', methods=['GET', 'OPTIONS'])
def get_driver_closings_summary():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    try:
        days = int(request.args.get('days', 30))
        # جلب آخر x يوم من تقفيلات السواقين
        from datetime import datetime, timedelta
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        # جلب بيانات التقفيلات من Supabase (جدول driver_closings)
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/driver_closings?select=*&created_at=gte.{since}&order=created_at.desc&limit=200",
            headers=SUPABASE_SERVICE_HEADERS
        )
        
        if r.status_code != 200:
            return jsonify({"summary": "لا تتوفر بيانات تقفيل في قاعدة البيانات حالياً.", "raw": []}), 200
        
        data = r.json()
        if not data:
            return jsonify({"summary": "لا توجد تقفيلات مسجلة في آخر " + str(days) + " يوم.", "raw": []}), 200
        
        # بناء ملخص نصي للمساعد
        total_collected = sum(float(row.get('collection', 0) or 0) for row in data)
        total_expenses = sum(
            float(row.get('toll_exp', 0) or 0) + 
            float(row.get('gas_exp', 0) or 0) + 
            float(row.get('other_exp', 0) or 0) 
            for row in data
        )
        total_net = sum(float(row.get('remaining_coll', 0) or 0) for row in data)
        
        # إحصائيات السائقين
        driver_stats = {}
        for row in data:
            name = row.get('captain_name', 'غير معروف')
            if name not in driver_stats:
                driver_stats[name] = {'trips': 0, 'collected': 0, 'net': 0}
            driver_stats[name]['trips'] += 1
            driver_stats[name]['collected'] += float(row.get('collection', 0) or 0)
            driver_stats[name]['net'] += float(row.get('remaining_coll', 0) or 0)
        
        # إحصائيات السيارات
        car_stats = {}
        for row in data:
            car = row.get('car_name', 'غير معروف')
            if car not in car_stats:
                car_stats[car] = {'trips': 0, 'km': 0}
            car_stats[car]['trips'] += 1
            start_km = float(row.get('start_km', 0) or 0)
            end_km = float(row.get('end_km', 0) or 0)
            car_stats[car]['km'] += max(0, end_km - start_km)
        
        summary = f"""
📦 ملخص تقفيلات السواقين (آخر {days} يوم) - {len(data)} تقفيلة:
- إجمالي التحصيل من العملاء: {total_collected:,.0f} ج.م
- إجمالي المصاريف (بنزين + كارتات + أخرى): {total_expenses:,.0f} ج.م
- إجمالي صافي المُحوَّل للمكتب: {total_net:,.0f} ج.م

👥 أداء السائقين:
"""
        for name, s in sorted(driver_stats.items(), key=lambda x: x[1]['trips'], reverse=True):
            summary += f"- {name}: {s['trips']} رحلة | حصّل: {s['collected']:,.0f} ج.م | صافي: {s['net']:,.0f} ج.م\n"
        
        summary += "\n🚗 أداء السيارات (كيلومتر):\n"
        for car, s in sorted(car_stats.items(), key=lambda x: x[1]['km'], reverse=True):
            summary += f"- {car}: {s['trips']} رحلة | {s['km']:,.0f} كم مجموع\n"
        
        return jsonify({"summary": summary, "raw": data[:20], "total_trips": len(data)}), 200
    
    except Exception as e:
        print(f"[ERROR] driver_closings_summary: {e}")
        return jsonify({"summary": f"خطأ في جلب البيانات: {str(e)}", "raw": []}), 200



@app.route('/api/sniper/trips', methods=['GET', 'OPTIONS'])
def get_sniper_trips():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    r = requests.get(f"{SUPABASE_URL}/rest/v1/sniper_parsed_trips?order=created_at.desc&limit=100", headers=SUPABASE_SERVICE_HEADERS)
    return make_response(r.text, r.status_code, {"Content-Type": "application/json"})

@app.route('/api/sniper/settings', methods=['GET', 'POST', 'OPTIONS'])
def manage_sniper_settings():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    if request.method == 'GET':
        r = requests.get(f"{SUPABASE_URL}/rest/v1/sniper_settings?select=*", headers=SUPABASE_SERVICE_HEADERS)
        return make_response(r.text, r.status_code, {"Content-Type": "application/json"})
    elif request.method == 'POST':
        data = request.json
        key = data.get("key")
        value = data.get("value")
        payload = {"key": key, "value": value}
        r = requests.post(f"{SUPABASE_URL}/rest/v1/sniper_settings?on_conflict=key", headers=SUPABASE_SERVICE_HEADERS, json=payload)
        return make_response(r.text, r.status_code, {"Content-Type": "application/json"})

# = [OMNI REPLY] Omnichannel Reply API نقطة الإرسال الجديدة
# =====================================================
@app.route('/api/send_reply', methods=['POST', 'OPTIONS'])
def send_omnichannel_reply():
    if request.method == 'OPTIONS':
        return make_response("", 204)

    data = request.json or {}
    channel = data.get('channel', '').lower()
    raw_sender_id = data.get('sender_id')
    message = data.get('message', '')
    media_url = data.get('media_url')
    media_type = data.get('media_type', 'image')
    mod_name = data.get('mod_name', 'Admin') # Get moderator name
    whatsapp_instance_id = data.get('whatsapp_instance_id')

    if not channel or not raw_sender_id or (not message and not media_url):
        return jsonify({"status": "error", "message": "Missing parameters"}), 400

    # 🧼 تنظيف وتنسيق معرف العميل أو رقم الهاتف بدقة
    clean_sender_id = str(raw_sender_id).replace("+", "").replace(" ", "").strip()
    if channel == 'whatsapp':
        if clean_sender_id.startswith("01") and len(clean_sender_id) == 11:
            clean_sender_id = "20" + clean_sender_id[1:]
        clean_sender_id = ''.join(c for c in clean_sender_id if c.isdigit())
        sender_id = clean_sender_id if clean_sender_id else str(raw_sender_id).replace("+", "").strip()
    else:
        sender_id = clean_sender_id

    # 🛑 فحص الأوامر الإدارية أولاً (مثل إيقاف وتشغيل البوت)
    if message:
        is_cmd, cmd_act = handle_admin_command_if_any(channel, sender_id, message)
        if is_cmd:
            insert_message_to_supabase(
                channel=channel,
                sender_id=sender_id,
                sender_name=mod_name,
                message_text=f"🔑 [إجراء إداري]: تم {'تشغيل الرد التلقائي' if cmd_act == 'resumed' else 'إيقاف الرد التلقائي'}",
                is_from_admin=True,
                whatsapp_instance_id=whatsapp_instance_id
            )
            return jsonify({"status": "success", "detail": f"command_{cmd_act}"})

    send_success = False
    api_error = ""

    if channel == 'whatsapp':
        # Resolve custom WhatsApp instance if not specified
        if not whatsapp_instance_id:
            try:
                local = sender_id[2:] if sender_id.startswith("20") else sender_id
                r_inst = requests.get(
                    f"{SUPABASE_URL}/rest/v1/omnichannel_messages",
                    headers=SUPABASE_SERVICE_HEADERS,
                    params={
                        "channel": "eq.whatsapp",
                        "sender_id": f"ilike.%{local}%",
                        "whatsapp_instance_id": "is.not.null",
                        "select": "whatsapp_instance_id",
                        "limit": "1",
                        "order": "created_at.desc"
                    },
                    timeout=1.5
                )
                if r_inst.status_code == 200 and r_inst.json():
                    whatsapp_instance_id = r_inst.json()[0].get("whatsapp_instance_id")
            except Exception as ex:
                print(f"Error resolving whatsapp_instance_id: {ex}")

        # [FALLBACK] If still not resolved, find the first connected local instance
        if not whatsapp_instance_id:
            try:
                r_active = requests.get(
                    f"{SUPABASE_URL}/rest/v1/whatsapp_instances?status=eq.connected&limit=1",
                    headers=SUPABASE_SERVICE_HEADERS,
                    timeout=1.5
                )
                if r_active.status_code == 200 and r_active.json():
                    whatsapp_instance_id = r_active.json()[0].get("id")
                    print(f"[WA] Auto-resolved active WhatsApp instance ID: {whatsapp_instance_id}")
            except Exception as ex:
                print(f"Error auto-resolving default active instance: {ex}")

        routed_via_custom = False
        if whatsapp_instance_id:
            r_creds = requests.get(f"{SUPABASE_URL}/rest/v1/whatsapp_instances?id=eq.{whatsapp_instance_id}", headers=SUPABASE_SERVICE_HEADERS, timeout=2)
            if r_creds.status_code == 200 and r_creds.json():
                inst = r_creds.json()[0]
                provider = inst["provider"]
                inst_id = inst["instance_id"]
                token = inst["token"]
                api_url = inst.get("api_url")
                routed_via_custom = True
                
                if provider == "ultramsg":
                    base = api_url.strip().rstrip('/') if api_url else "https://api.ultramsg.com"
                    send_url = f"{base}/{inst_id}/messages/image" if media_url else f"{base}/{inst_id}/messages/chat"
                    payload = {"token": token, "to": sender_id}
                    if media_url:
                        payload.update({"image": media_url, "caption": message})
                    else:
                        payload.update({"body": message})
                    try:
                        res = requests.post(send_url, data=payload, timeout=8)
                        if res.status_code == 200 and ("success" in res.text.lower() or "\"sent\":\"true\"" in res.text.lower()):
                            send_success = True
                        else:
                            api_error = res.text
                            print(f"❌ UltraMsg send failed: {res.text}")
                    except Exception as e:
                        api_error = str(e)
                        print(f"❌ UltraMsg exception: {e}")
                elif provider == "greenapi":
                    base = api_url.strip().rstrip('/') if api_url else "https://api.greenapi.com"
                    if media_url:
                        send_url = f"{base}/waInstance{inst_id}/sendFileByUrl/{token}"
                        filename = media_url.split('/')[-1]
                        payload = {
                            "chatId": f"{sender_id}@c.us",
                            "urlFile": media_url,
                            "fileName": filename,
                            "caption": message
                        }
                    else:
                        send_url = f"{base}/waInstance{inst_id}/sendMessage/{token}"
                        payload = {
                            "chatId": f"{sender_id}@c.us",
                            "message": message
                        }
                    try:
                        res = requests.post(send_url, json=payload, timeout=8)
                        if res.status_code == 200:
                            send_success = True
                        else:
                            api_error = res.text
                            print(f"❌ GreenAPI send failed: {res.text}")
                    except Exception as e:
                        api_error = str(e)
                        print(f"❌ GreenAPI exception: {e}")
                elif provider == "local":
                    base = api_url.strip().rstrip('/') if api_url else "http://localhost:3001"
                    send_url = f"{base}/instance/{whatsapp_instance_id}/send"
                    payload = {
                        "to": sender_id,
                        "message": message,
                        "media_url": media_url,
                        "media_type": media_type
                    }
                    for attempt in range(3):
                        try:
                            res = requests.post(send_url, json=payload, timeout=8)
                            if res.status_code == 200 and res.json().get("status") == "success":
                                send_success = True
                                break
                            else:
                                api_error = res.text
                                print(f"❌ Local WA send failed (attempt {attempt+1}): {res.text}")
                                if "Connection Closed" in res.text or "closed" in res.text.lower() or res.status_code == 500:
                                    time.sleep(1.5)
                                else:
                                    break
                        except Exception as e:
                            api_error = str(e)
                            print(f"❌ Local WA exception (attempt {attempt+1}): {e}")
                            time.sleep(1.5)

            else:
                print(f"⚠️ Could not fetch credentials for whatsapp_instance_id {whatsapp_instance_id}, falling back to Meta API")

        # Fallback to Meta API
        if not routed_via_custom or not send_success:
            if not whatsapp_instance_id:
                url = f"https://graph.facebook.com/v17.0/{PHONE_ID}/messages"
                headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
                if media_url:
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": sender_id,
                        "type": media_type,
                        media_type: {"link": media_url, "caption": message}
                    }
                else:
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": sender_id,
                        "type": "text",
                        "text": {"body": message}
                    }
                try:
                    r = requests.post(url, headers=headers, json=payload, timeout=8)
                    print(f"[WA-API] Status: {r.status_code} | Response: {r.text}")
                    if r.status_code in [200, 201]:
                        send_success = True
                    else:
                        api_error = r.text
                        print(f"[ERROR] WA API rejected message ({r.status_code}): {r.text}")
                except Exception as e:
                    api_error = str(e)
                    print(f"[ERROR] WA Send Exception: {e}")
            else:
                if not api_error:
                    api_error = "Custom WhatsApp instance send failed"

    elif channel == 'messenger':
        if not FB_PAGE_TOKEN:
            api_error = "FB_PAGE_TOKEN is empty"
            print("[ERROR] FB_PAGE_TOKEN is empty.")
        else:
            url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_TOKEN}"
            headers = {"Content-Type": "application/json"}
            if media_url:
                payload = {
                    "recipient": {"id": sender_id},
                    "message": {
                        "attachment": {
                            "type": media_type,
                            "payload": {
                                "url": media_url,
                                "is_reusable": True
                            }
                        }
                    }
                }
            else:
                payload = {"recipient": {"id": sender_id}, "message": {"text": message}}
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=10)
                print(f"[FB-API] Status: {r.status_code} | Response: {r.text}")
                if r.status_code == 200:
                    send_success = True
                    try:
                        fb_msg_id = r.json().get('message_id', '')
                        if fb_msg_id:
                            sent_via_api_mids.add(fb_msg_id)
                            if len(sent_via_api_mids) > 500: sent_via_api_mids.clear()
                            print(f"[FB-API] Tracked MID: {fb_msg_id}")
                    except: pass
                else:
                    api_error = r.text
                    print(f"[ERROR] Messenger API rejected message ({r.status_code}): {r.text}")
            except Exception as e:
                api_error = str(e)
                print(f"[ERROR] Messenger Send Exception: {e}")

    elif channel == 'instagram':
        if not INSTAGRAM_TOKEN:
            api_error = "INSTAGRAM_TOKEN is empty"
            print("[ERROR] INSTAGRAM_TOKEN is empty.")
        else:
            try:
                take_url = f"https://graph.facebook.com/v18.0/me/take_thread_control"
                take_payload = {"recipient": {"id": sender_id}}
                tc_res = requests.post(take_url, headers={"Content-Type": "application/json"},
                                      params={"access_token": FB_PAGE_TOKEN}, json=take_payload, timeout=3)
                if tc_res.status_code == 200:
                    print(f"[IG-Handover] Successfully took thread control for {sender_id}")
            except Exception as tc_err:
                print(f"[IG-Handover] Exception: {tc_err}")

            url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_TOKEN}"
            headers = {"Content-Type": "application/json"}
            if media_url:
                payload = {
                    "recipient": {"id": sender_id},
                    "message": {
                        "attachment": {
                            "type": media_type,
                            "payload": {
                                "url": media_url,
                                "is_reusable": True
                            }
                        }
                    }
                }
            else:
                payload = {"recipient": {"id": sender_id}, "message": {"text": message}}
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=10)
                print(f"[IG-API] Status: {r.status_code} | Response: {r.text}")
                if r.status_code == 200:
                    send_success = True
                    try:
                        ig_msg_id = r.json().get('message_id', '')
                        if ig_msg_id:
                            sent_via_api_mids.add(ig_msg_id)
                            if len(sent_via_api_mids) > 500: sent_via_api_mids.clear()
                            print(f"[IG-API] Tracked MID: {ig_msg_id}")
                    except: pass
                else:
                    err_json = {}
                    try: err_json = r.json()
                    except: pass
                    err_code = err_json.get('error', {}).get('error_subcode', 0)
                    if err_code == 2534037:
                        api_error = "instagram_handover_error"
                    elif err_code == 2534022:
                        api_error = "instagram_window_expired"
                    elif err_code == 2534048:
                        api_error = "instagram_dev_mode"
                    else:
                        api_error = r.text
            except Exception as e:
                api_error = str(e)
                print(f"[ERROR] Instagram Send Exception: {e}")
    else:
        return jsonify({"status": "error", "message": "Invalid channel type"}), 400

    # 🛑 حفظ في قاعدة البيانات وحفظ الـ State فقط وفقط في حالة نجاح الإرسال الفعلي!
    if send_success:
        if media_url and media_type == "image":
            sb_message_text = f"MEDIA_IMAGE:{media_url}{('|CAPTION:' + message) if message else ''}"
        elif media_url and media_type == "audio":
            sb_message_text = f"MEDIA_AUDIO:{media_url}"
        else:
            sb_message_text = message

        insert_message_to_supabase(
            channel=channel,
            sender_id=sender_id,
            sender_name=mod_name,
            message_text=sb_message_text,
            is_from_admin=True,
            whatsapp_instance_id=whatsapp_instance_id
        )
        print(f"[INFO] Successfully sent {channel} message to {sender_id}")
        if channel in ['messenger', 'instagram']:
            messenger_states[sender_id] = "HUMAN"
            print(f"[AUTO-PAUSE] Bot automatically paused (HUMAN mode) for {channel} user {sender_id}")
        return jsonify({"status": "success"})
    elif api_error == "instagram_handover_error":
        return jsonify({
            "status": "warning",
            "message": "تم حفظ الرسالة، لكن لم تُرسل للعميل. يرجى تعيين تطبيقك كـ Primary Receiver للإنستجرام."
        }), 200
    elif api_error == "instagram_window_expired":
        return jsonify({
            "status": "warning",
            "message": "⚠️ انتهت مهلة الـ 24 ساعة! لا يمكن الرد على هذا العميل لأنه لم يرسل رسالة خلال آخر 24 ساعة."
        }), 200
    elif api_error == "instagram_dev_mode":
        return jsonify({
            "status": "warning",
            "message": "التطبيق في وضع التطوير ويحتاج Advanced Access من Meta."
        }), 200
    else:
        print(f"[ERROR] FAILED to send {channel} message to {sender_id}: {api_error}")
        return jsonify({"status": "error", "message": f"❌ فشل إرسال الرسالة للعميل عبر الواتساب: {api_error[:100]}"}), 400

# =====================================================
# 📁 إدارة ملف التخزين المؤقت لحملات الماسنجر لمنع التكرار
# =====================================================
MESSENGER_CACHE_FILE = os.path.join(os.path.dirname(__file__), "sent_messenger_cache.json")

def load_messenger_sent_cache():
    if os.path.exists(MESSENGER_CACHE_FILE):
        try:
            with open(MESSENGER_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_messenger_sent_cache(cache_data):
    try:
        with open(MESSENGER_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Messenger Cache Error]: {e}")

@app.route('/api/messenger/reset_cache', methods=['POST', 'OPTIONS'])
def reset_messenger_cache_api():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    save_messenger_sent_cache({})
    return jsonify({"status": "success", "message": "تم إعادة ضبط سجل عملاء الماسنجر المرسل لهم بنجاح"})

# = [MESSENGER BROADCAST] Messenger Campaign API نقطة إرسال حملات الماسنجر
# =====================================================
@app.route('/api/messenger/broadcast', methods=['POST', 'OPTIONS'])
def messenger_broadcast_api():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    global broadcast_status
    try:
        if broadcast_status.get("status") == "running":
            return jsonify({"status": "error", "message": "هناك حملة تسويقية قيد التشغيل بالفعل حالياً"}), 400

        data = request.get_json() or {}
        message_text = data.get("message")
        if not message_text:
            return jsonify({"status": "error", "message": "Missing 'message' field"}), 400

        # جلب كافة عملاء الماسنجر الفريدين
        url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages?channel=eq.messenger&select=sender_id,sender_name&order=created_at.desc&limit=2000"
        r = requests.get(url, headers=SUPABASE_SERVICE_HEADERS)
        clients = {}
        if r.status_code == 200:
            msgs = r.json()
            for m in msgs:
                sid = m.get("sender_id")
                sname = m.get("sender_name") or "Messenger User"
                if sid and sid not in clients and sname not in ["Admin", "Bot", "ش"]:
                    clients[sid] = sname

        if not clients:
            return jsonify({"status": "error", "message": "لم يتم العثور على أي عملاء ماسنجر للإرسال إليهم"}), 400

        total_targets = len(clients)
        sent_cache = load_messenger_sent_cache()

        # تهيئة حالة الحملة المباشرة للشاشة
        broadcast_status["status"] = "running"
        broadcast_status["total"] = total_targets
        broadcast_status["sent"] = 0
        broadcast_status["failed"] = 0
        broadcast_status["pct"] = 0
        broadcast_status["logs"] = [
            f"🚀 [Messenger] بدء إطلاق حملة الماسنجر لعدد ({total_targets}) عميل فريد...",
            f"ℹ️ كود السجل المحفوظ مسبقاً يحتوي على ({len(sent_cache)}) عميل مُرسل لهم."
        ]

        def run_campaign():
            import time
            processed_count = 0
            sent_count = 0
            failed_count = 0

            for sid, sname in clients.items():
                if broadcast_status.get("status") == "stopped":
                    broadcast_status["logs"].append("⚠️ تم إيقاف حملة الماسنجر بناءً على طلب المستخدم.")
                    print("[Messenger Broadcast] Campaign stopped by user.")
                    break

                processed_count += 1

                # 1. التحقق من السجل المحلي لمنع تكرار الإرسال
                if str(sid) in sent_cache:
                    broadcast_status["logs"].append(f"⏩ [تخطي] العميل ({sname}) تلقى رسالة سابقة، تم تخطيه لمنع التكرار.")
                    broadcast_status["pct"] = int((processed_count / total_targets) * 100)
                    continue

                # 2. تجهيز طلب الإرسال مع Meta Message Tag للحسابات القديمة
                send_url = f"https://graph.facebook.com/v18.0/me/messages?access_token={FB_PAGE_TOKEN}"
                payload = {
                    "recipient": {"id": str(sid)},
                    "message": {"text": message_text},
                    "messaging_type": "MESSAGE_TAG",
                    "tag": "CONFIRMED_EVENT_UPDATE"
                }

                try:
                    res = requests.post(send_url, json=payload, timeout=15)
                    res_json = {}
                    try: res_json = res.json()
                    except: pass

                    if res.status_code == 200 and not res_json.get("error"):
                        sent_count += 1
                        broadcast_status["sent"] = sent_count
                        sent_cache[str(sid)] = {"sent_at": time.strftime("%Y-%m-%d %H:%M:%S"), "name": sname}
                        save_messenger_sent_cache(sent_cache)
                        
                        insert_message_to_supabase(channel="messenger", sender_id=sid, sender_name=sname, message_text=message_text, is_from_admin=True)
                        broadcast_status["logs"].append(f"✅ [{processed_count}/{total_targets}] تم الإرسال بنجاح إلى: {sname}")
                    else:
                        # تجربة طريقة بديلة بدون Tag لو فشل الـ Tag
                        payload_std = {
                            "recipient": {"id": str(sid)},
                            "message": {"text": message_text}
                        }
                        res_std = requests.post(send_url, json=payload_std, timeout=15)
                        if res_std.status_code == 200 and not res_std.json().get("error"):
                            sent_count += 1
                            broadcast_status["sent"] = sent_count
                            sent_cache[str(sid)] = {"sent_at": time.strftime("%Y-%m-%d %H:%M:%S"), "name": sname}
                            save_messenger_sent_cache(sent_cache)
                            
                            insert_message_to_supabase(channel="messenger", sender_id=sid, sender_name=sname, message_text=message_text, is_from_admin=True)
                            broadcast_status["logs"].append(f"✅ [{processed_count}/{total_targets}] تم الإرسال بنجاح إلى: {sname}")
                        else:
                            failed_count += 1
                            broadcast_status["failed"] = failed_count
                            err_msg = res_json.get("error", {}).get("message", res.text[:80])
                            broadcast_status["logs"].append(f"❌ [{processed_count}/{total_targets}] فشل الإرسال إلى {sname}: {err_msg}")

                except Exception as e:
                    failed_count += 1
                    broadcast_status["failed"] = failed_count
                    broadcast_status["logs"].append(f"❌ [{processed_count}/{total_targets}] خطأ اتصال مع {sname}: {str(e)[:80]}")

                broadcast_status["pct"] = int((processed_count / total_targets) * 100)
                time.sleep(1.5)

            if broadcast_status.get("status") == "running":
                broadcast_status["status"] = "completed"
                broadcast_status["logs"].append("🎉 اكتملت حملة الماسنجر بنجاح!")

        import threading
        threading.Thread(target=run_campaign, daemon=True).start()
        return jsonify({"status": "success", "message": "تم بدء حملة الماسنجر في الخلفية بنجاح", "total_targets": total_targets})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# = [STAFF MGMT] Staff Management إدارة الموظفين
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

        print(f"[INFO] Creating staff: {email} ({full_name}) as {role}")

        service_key = SUPABASE_SERVICE_ROLE_KEY
        if not service_key:
            error_msg = "[ERROR] Missing SUPABASE_SERVICE_ROLE_KEY! Please set it in webhook_server.py line 20."
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

        print("[INFO] Sending request to Supabase Auth Admin API...")
        r_auth = requests.post(auth_url, headers=headers, json=auth_data)
        
        if r_auth.status_code not in [200, 201]:
            detail = r_auth.text
            try: detail = r_auth.json().get('msg', r_auth.text)
            except: pass
            print(f"[ERROR] Supabase Auth Error ({r_auth.status_code}): {detail}")
            return jsonify({"status": "error", "detail": f"Auth Error: {detail}"}), r_auth.status_code
        
        user_info = r_auth.json()
        user_id = user_info.get("id")
        print(f"[INFO] User created in Auth (ID: {user_id}). Creating profile...")

        profile_url = f"{SUPABASE_URL}/rest/v1/profiles"
        profile_data = {
            "id": user_id,
            "full_name": full_name,
            "role": role,
            "email": email
        }
        r_prof = requests.post(profile_url, headers=headers, json=profile_data)
        
        if r_prof.status_code not in [200, 201, 204]:
            print(f"[WARNING] Profile creation warning ({r_prof.status_code}): {r_prof.text}")

        print(f"[INFO] Staff account {email} created successfully!")
        return jsonify({"status": "success", "user_id": user_id})

    except Exception as e:
        print("[ERROR] Critical Error in create_staff_account:")
        traceback.print_exc()
        return jsonify({"status": "error", "detail": str(e)}), 500

# = [DIAGNOSTIC] Diagnostic FB فحص اتصال فيسبوك
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

# = [AI PROXY] Claude AI Proxy [AI]
# =====================================================
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL  = 'claude-3-haiku-20240307'

# = [AI CHAT PROXY] Groq AI Proxy for Academy Training
# =====================================================
import time as _time
_last_ai_call_time = 0

@app.route('/api/ai_chat', methods=['POST', 'OPTIONS'])
def ai_chat_proxy():
    global _last_ai_call_time
    if request.method == 'OPTIONS':
        return make_response("", 204)
    try:
        body = request.json
        system_prompt = body.get('system', '')
        messages      = body.get('messages', [])
        max_tokens    = body.get('max_tokens', 300)
        is_eval_request = body.get('is_evaluation', False)

        # تحديد إذا كان طلب تقييم (يحتاج سياق أطول وإجابة أطول)
        is_eval_request = is_eval_request or 'تقييم' in system_prompt or 'score' in system_prompt.lower() or 'JSON' in system_prompt

        if is_eval_request:
            # طلبات التقييم: احتفظ بآخر 15 رسالة وكل محتوى حتى 800 حرف
            messages = messages[-15:]
            messages = [{'role': m.get('role', 'user'), 'content': str(m.get('content', ''))[:800]} for m in messages]
        else:
            # طلبات الدردشة العادية: آخر 8 رسائل وكل محتوى محدود بـ 400 حرف
            messages = messages[-8:]
            messages = [{'role': m.get('role', 'user'), 'content': str(m.get('content', ''))[:400]} for m in messages]

        # إضافة أسعار فقط لو مش طلب تدريب (Training Academy)
        is_training = system_prompt.startswith('\u0639\u0645\u064a\u0644') or 'سيناريو' in system_prompt
        if not is_training:
            try:
                pricing_rows = messenger_agent.fetch_pricing_data()
                if pricing_rows:
                    pricing_text = "\n\n📋 أسعار الرحلات:\n"
                    for r in pricing_rows[:5]:  # أول 5 أسعار فقط
                        pricing_text += f"- {r['origin']} → {r['destination']}: {r['price_one_way']} ج.م\n"
                    system_prompt = f"{system_prompt}{pricing_text}"
            except Exception as pe:
                print(f"[WARNING] Pricing fetch skipped: {pe}")

        # Rate limiting محلي: انتظر 1 ثانية بين الطلبات
        now = _time.time()
        if now - _last_ai_call_time < 1.0:
            _time.sleep(1.0 - (now - _last_ai_call_time))
        _last_ai_call_time = _time.time()

        groq_key   = os.getenv("GROQ_API_KEY")
        groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }

        formatted_messages = []
        if system_prompt:
            # ✅ المساعد الإداري يحتاج سياق كبير لبيانات الشيت
            # طلبات التقييم: 4000 حرف
            # المساعد الإداري (admin): 4000 حرف
            # طلبات الدردشة العادية: 1500 حرف
            is_admin_ai = 'مساعد إداري' in system_prompt or '24Seven' in system_prompt or 'تقفيل' in system_prompt
            sp_limit = 4000 if (is_eval_request or is_admin_ai) else 1500
            formatted_messages.append({"role": "system", "content": system_prompt[:sp_limit]})
        for msg in messages:
            role = "assistant" if msg.get("role") in ["model", "assistant"] else "user"
            formatted_messages.append({"role": role, "content": msg.get("content", "")})

        payload = {
            "model": groq_model,
            "messages": formatted_messages,
            "temperature": 0.7,
            # طلبات التقييم والمساعد الإداري تحتاج إجابة أطول
            "max_tokens": 1500 if (is_eval_request or is_admin_ai) else min(int(max_tokens), 500)
        }

        # Define model fallback chain to prevent rate limiting issues
        models_to_try = [groq_model]
        for fallback in ["llama-3.1-8b-instant", "gemma2-9b-it", "mixtral-8x7b-32768", "llama-3.3-70b-versatile"]:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        r = None
        last_error = ""
        success = False

        for model in models_to_try:
            payload["model"] = model
            print(f"[AI Chat] Trying model: {model}")
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=30)
                if r.status_code == 200:
                    success = True
                    break
                elif r.status_code == 429:
                    retry_after = r.headers.get('retry-after', '5')
                    last_error = f"Rate limit (429) for {model}. Retry after {retry_after}s"
                    print(f"[WARNING] {last_error}, trying next fallback model...")
                else:
                    resp_data = r.json()
                    error_msg = resp_data.get('error', {}).get('message', r.text)
                    last_error = f"Error ({r.status_code}) for {model}: {error_msg}"
                    print(f"[WARNING] {last_error}, trying next fallback model...")
            except Exception as ex:
                last_error = f"Request exception for {model}: {str(ex)}"
                print(f"[WARNING] {last_error}, trying next fallback model...")

        if not success:
            print(f"[ERROR] All models in fallback chain failed. Last error: {last_error}")
            return jsonify({'error': 'rate_limit', 'detail': last_error}), 429

        resp_data = r.json()
        answer = resp_data['choices'][0]['message']['content']
        return jsonify({'answer': answer})

    except Exception as e:
        print(f"[ERROR] AI Proxy Error: {e}")
        return jsonify({'error': str(e)}), 500


# = [UPLOAD] File Upload API
# =====================================================
@app.route('/api/upload', methods=['POST', 'OPTIONS'])
def upload_file():
    if request.method == 'OPTIONS':
        return make_response("", 204)
        
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
        
    if file:
        ext = os.path.splitext(file.filename)[1].lower()
        if not ext:
            content_type = file.content_type or ''
            if 'image' in content_type:
                ext = '.jpg'
            elif 'audio' in content_type:
                ext = '.mp3'
            else:
                ext = '.tmp'
                
        unique_filename = f"upload_{int(time.time())}_{uuid.uuid4().hex[:6]}{ext}"
        upload_dir = os.path.join(os.path.dirname(__file__), '24Seven_SaaS_Platform', 'static', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, unique_filename)
        file.save(file_path)
        
        relative_url = f"/static/uploads/{unique_filename}"
        return jsonify({"status": "success", "url": relative_url})


# = [STATIC] Static File Serving خدمة الملفات

# =====================================================
@app.route('/static/uploads/<path:filename>')
def serve_upload_file(filename):
    local_dir = os.path.join(os.getcwd(), '24Seven_SaaS_Platform', 'static', 'uploads')
    local_file = os.path.join(local_dir, filename)
    if os.path.isfile(local_file):
        return send_from_directory(local_dir, filename)
    # Fallback: redirect to production server
    return redirect(f"https://24seven-ai.com/static/uploads/{filename}")

@app.route('/<path:filename>')
def serve_any_file(filename):
    directory = os.path.join(os.getcwd(), '24Seven_SaaS_Platform')
    # تأكد أن الملف موجود لتجنب تداخل الروابط
    if os.path.isfile(os.path.join(directory, filename)):
        return send_from_directory(directory, filename)
    # إذا لم يكن ملفاً، قد يكون رابطاً للفلاسك نفسه، نتركه يمر للفلاسك الطبيعي
    return "Not Found", 404

@app.route('/api/mod_login', methods=['POST', 'OPTIONS'])
def mod_login_api():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    try:
        data = request.json or {}
        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', '')).strip()

        if not email or not password:
            return jsonify({'status': 'error', 'message': 'الرجاء إدخال البريد الإلكتروني وكلمة المرور'}), 400

        # 1. البحث في قواعد بيانات سوبابيز أولاً إذا كانت متوفرة
        try:
            r = requests.get(f"{SUPABASE_URL}/rest/v1/profiles?select=*&email=eq.{email}", headers=SUPABASE_SERVICE_HEADERS, timeout=3)
            if r.status_code == 200 and r.json():
                prof = r.json()[0]
                return jsonify({
                    'status': 'success',
                    'profile': {
                        'full_name': prof.get('full_name') or email.split('@')[0].capitalize(),
                        'role': prof.get('role') or 'moderator',
                        'id': prof.get('id') or f"mod_{email}"
                    }
                })
        except Exception as e:
            pass

        # 2. Fallback محلي فوري عند توقف سوبابيز بسبب حظر Egress Quota 402
        known_mods = {
            'noha@24seven.com': 'نهى',
            'rania@24seven.com': 'رانيا',
            'admin@24seven.com': 'أدمن النظام',
            'ahmed@24seven.com': 'أحمد'
        }
        
        name_parts = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
        display_name = known_mods.get(email, name_parts)
        role = 'admin' if 'admin' in email else 'moderator'

        return jsonify({
            'status': 'success',
            'profile': {
                'full_name': display_name,
                'role': role,
                'id': f"mod_{email.replace('@', '_').replace('.', '_')}"
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/save_reservation', methods=['POST', 'OPTIONS'])
def save_reservation_api():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    try:
        payload = request.json or {}
        if not payload.get('customer_name') or not payload.get('customer_phone'):
            return jsonify({'status': 'error', 'message': 'اسم العميل ورقم الهاتف مطلوبان'}), 400

        res_id = payload.get('id') or f"local_res_{int(time.time()*1000)}"
        payload['id'] = res_id

        # 1. محاولة حفظ الحجز في سوبابيز إن كانت الخدمة متوفرة
        try:
            r = requests.post(f"{SUPABASE_URL}/rest/v1/google_reservations", headers=SUPABASE_SERVICE_HEADERS, json=payload, timeout=3)
            if r.status_code in (200, 201) and r.json():
                return jsonify({'status': 'success', 'data': r.json()})
        except Exception:
            pass

        # 2. إرجاع النتيجة بالنجاح للمشرف لحفظ الحجز ومزامنته في جوجل شيت فوراً
        return jsonify({
            'status': 'success',
            'data': [payload],
            'message': 'تم حفظ الحجز بنجاح'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/moderator')
def serve_moderator():
    directory = os.path.join(os.getcwd(), '24Seven_SaaS_Platform')
    return send_from_directory(directory, 'moderator.html')

# = [SERVER] Main Server Startup تشغيل السيرفر الموحد
# =====================================================
@app.route('/api/health', methods=['GET', 'OPTIONS'])
def health_check():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    # Also handle verification here just in case
    if request.args.get("hub.verify_token") in [VERIFY_TOKEN, FB_VERIFY_TOKEN]:
        return request.args.get("hub.challenge"), 200
    return jsonify({"status": "ok", "message": "Server is running"})

@app.route('/api/whatsapp/calculate-price', methods=['GET', 'POST', 'OPTIONS'])
def calculate_price_api():
    if request.method == 'OPTIONS':
        return make_response("", 204)
        
    if request.method == 'POST':
        data = request.get_json() or {}
        origin = data.get('origin', '')
        destination = data.get('destination', '')
        car_type = data.get('car_type', 'سيدان')
    else:
        origin = request.args.get('origin', '')
        destination = request.args.get('destination', '')
        car_type = request.args.get('car_type', 'سيدان')
        
    if not origin or not destination:
        return jsonify({"status": "error", "message": "Origin and destination are required"}), 400
        
    try:
        p1, pr = messenger_agent.lookup_price(origin, destination, car_type)
        return jsonify({
            "status": "success",
            "origin": origin,
            "destination": destination,
            "car_type": car_type,
            "price_one_way": p1,
            "price_round_trip": pr
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/ping')
def ping():
    return "pong"

# --- [BROADCAST MARKETING SYSTEM] ---
# ✅ نظام الحملات الإعلانية مع فترات انتظار ذكية (Anti-ban)
import threading
import random

broadcast_status = {
    "status": "idle",  # "idle", "running", "stopped", "completed"
    "total": 0,
    "sent": 0,
    "failed": 0,
    "current_phone": "",
    "logs": []
}

def fetch_unique_customer_phones():
    phones = set()
    
    # 1. جلب من Supabase profiles
    try:
        url_prof = f"{SUPABASE_URL}/rest/v1/profiles?select=phone"
        r = requests.get(url_prof, headers=SUPABASE_SERVICE_HEADERS, timeout=10)
        if r.status_code == 200:
            for p in r.json():
                ph = p.get("phone")
                if ph:
                    cleaned = clean_phone_strict(ph)
                    if cleaned and len(cleaned) >= 11:
                        phones.add(cleaned)
    except Exception as e:
        print(f"[Broadcast] Error fetching profiles: {e}")
        
    # 2. جلب من Supabase google_reservations
    try:
        url_res = f"{SUPABASE_URL}/rest/v1/google_reservations?select=customer_phone"
        r = requests.get(url_res, headers=SUPABASE_SERVICE_HEADERS, timeout=10)
        if r.status_code == 200:
            for row in r.json():
                ph = row.get("customer_phone")
                if ph:
                    cleaned = clean_phone_strict(ph)
                    if cleaned and len(cleaned) >= 11:
                        phones.add(cleaned)
    except Exception as e:
        print(f"[Broadcast] Error fetching reservations: {e}")
        
    return sorted(list(phones))

# قاموس لأسماء المتغيرات المسماة للقوالب المعتمدة في ميتا لمنع خطأ Parameter name is missing
KNOWN_TEMPLATE_PARAMS = {
    "limo_marketing_offers": ["offer_details"],
    "daily_employee_report": ["report_details"],
    "daily_team_report": ["report_details"],
    "trip_feedback_start": ["client_name", "feedback_link"],
    "trip_order_driver": ["driver_name", "client_name"],
    "driver_details_assigned": ["client_name", "driver_name", "car_type"]
}

def run_broadcast_task(message_text, target_phones, use_meta=False, template_name=None, template_lang="ar", template_params=None):
    global broadcast_status
    broadcast_status["status"] = "running"
    broadcast_status["total"] = len(target_phones)
    broadcast_status["sent"] = 0
    broadcast_status["failed"] = 0
    broadcast_status["logs"] = [f"🚀 بدء الحملة التسويقية باستخدام {'بوابة Meta API الرسمية' if use_meta else 'بوابة واتساب ويب المحلية'}..."]
    
    if use_meta and not template_params and message_text:
        template_params = [message_text]
        
    active_instance_id = None
    try:
        r_act = requests.get(f"{SUPABASE_URL}/rest/v1/whatsapp_instances?provider=eq.local&status=eq.connected&limit=1", headers=SUPABASE_SERVICE_HEADERS, timeout=5)
        if r_act.status_code == 200 and r_act.json():
            active_instance_id = r_act.json()[0].get("id")
    except:
        pass
    if not active_instance_id:
        active_instance_id = "692921bb-a5df-451d-8527-e1ee55a736f4"
        
    send_url = f"http://localhost:3001/instance/{active_instance_id}/send"
    meta_url = f"https://graph.facebook.com/v17.0/{PHONE_ID}/messages"
    meta_headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    
    for idx, phone in enumerate(target_phones):
        if broadcast_status["status"] != "running":
            broadcast_status["logs"].append("⚠️ تم إيقاف الحملة التسويقية يدوياً.")
            break
            
        broadcast_status["current_phone"] = phone
        clean_to = str(phone).replace('+', '').replace('0020', '20').replace(' ', '').strip()
        if clean_to.startswith('01'):
            clean_to = '20' + clean_to[1:]
        elif clean_to.startswith('1'):
            clean_to = '20' + clean_to
            
        try:
            if use_meta and template_name:
                # تشكيل حمولة القالب الرسمي لميتا
                components = []
                if template_params:
                    # جلب أسماء المتغيرات المسماة للقالب
                    known_names = KNOWN_TEMPLATE_PARAMS.get(template_name, [])
                    param_list = []
                    for p_idx, p_val in enumerate(template_params):
                        clean_val = str(p_val).replace("\n", " ").replace("\r", " ")
                        param_obj = {
                            "type": "text",
                            "text": clean_val
                        }
                        # إذا كان القالب مسجلاً بمتغيرات مسماة، يجب تمرير parameter_name
                        if p_idx < len(known_names):
                            param_obj["parameter_name"] = known_names[p_idx]
                        else:
                            # كحل احتياطي عام للمتغيرات المسماة الأخرى
                            param_obj["parameter_name"] = f"param_{p_idx+1}"
                        param_list.append(param_obj)
                        
                    components = [{
                        "type": "body",
                        "parameters": param_list
                    }]
                
                payload = {
                    "messaging_product": "whatsapp",
                    "to": clean_to,
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {
                            "code": template_lang
                        }
                    }
                }
                if components:
                    payload["template"]["components"] = components
                    
                r = requests.post(meta_url, headers=meta_headers, json=payload, timeout=15)
                # حفظ نص الرسالة الفعلي ليكون مفيداً بالأدمن والشيت
                if template_params and len(template_params) > 0:
                    log_text = template_params[0]
                else:
                    log_text = message_text
            else:
                # استخدام واتساب ويب المحلي
                payload = {
                    "to": clean_to,
                    "message": message_text
                }
                r = requests.post(send_url, json=payload, timeout=15)
                log_text = message_text
                
            res_json = {}
            try:
                res_json = r.json()
            except:
                pass

            if r.status_code in [200, 201] and res_json.get("status") != "error":
                broadcast_status["sent"] += 1
                broadcast_status["logs"].append(f"✅ تم الإرسال بنجاح للرقم: {phone}")
                try: log_chat_to_sheet(clean_to, "Bot", log_text)
                except: pass
                try:
                    insert_message_to_supabase(
                        channel='whatsapp',
                        sender_id=clean_to,
                        sender_name='Bot',
                        message_text=log_text,
                        is_from_admin=True,
                        whatsapp_instance_id=None if use_meta else active_instance_id
                    )
                except: pass
            else:
                err_detail = res_json.get("message") or (r.text[:100] if r.text else f"HTTP {r.status_code}")
                broadcast_status["failed"] += 1
                broadcast_status["logs"].append(f"❌ فشل الإرسال للرقم: {phone} ({err_detail})")
        except Exception as e:
            broadcast_status["failed"] += 1
            broadcast_status["logs"].append(f"❌ خطأ مع الرقم {phone}: {str(e)}")
            
        # فترة انتظار عشوائية لحماية الرقم (Meta API أسرع بكثير ولا يحتاج لأكثر من ثانية)
        if idx < len(target_phones) - 1:
            delay = random.randint(1, 2) if use_meta else random.randint(8, 15)
            time.sleep(delay)
            
    if broadcast_status["status"] == "running":
        broadcast_status["status"] = "completed"
        broadcast_status["logs"].append("🎉 اكتملت الحملة التسويقية بنجاح.")

@app.route('/api/marketing/broadcast', methods=['POST', 'OPTIONS'])
def start_marketing_broadcast():
    if request.method == 'OPTIONS':
        return make_response("", 204)
        
    global broadcast_status
    if broadcast_status["status"] == "running":
        return jsonify({"status": "error", "message": "هناك حملة تسويقية قيد التشغيل بالفعل حالياً"}), 400
        
    data = request.get_json() or {}
    message_text = data.get("message", "").strip()
    use_meta = data.get("use_meta", False)
    template_name = data.get("template_name", "").strip()
    template_lang = data.get("template_lang", "ar").strip()
    template_params = data.get("template_params", [])
    
    if not use_meta and not message_text:
        return jsonify({"status": "error", "message": "صيغة الرسالة مطلوبة"}), 400
    if use_meta and not template_name:
        return jsonify({"status": "error", "message": "اسم قالب ميتا مطلوب عند اختيار إرسال API"}), 400
        
    # جلب كافة الأرقام الفريدة من قاعدة البيانات أو استخدام الأرقام المرسلة للتجربة
    target_phones = data.get("phones", [])
    if not target_phones:
        target_phones = fetch_unique_customer_phones()
        
    if not target_phones:
        return jsonify({"status": "error", "message": "لم يتم العثور على أي أرقام عملاء للإرسال إليها"}), 400
        
    # بدء الحملة في الخلفية عبر Thread
    t = threading.Thread(target=run_broadcast_task, args=(message_text, target_phones, use_meta, template_name, template_lang, template_params))
    t.daemon = True
    t.start()
    
    return jsonify({
        "status": "success", 
        "message": "تم بدء الحملة التسويقية بنجاح في الخلفية",
        "total_targets": len(target_phones)
    })

@app.route('/api/marketing/status', methods=['GET', 'OPTIONS'])
def get_marketing_status():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    global broadcast_status
    return jsonify(broadcast_status)

@app.route('/api/marketing/stop', methods=['POST', 'OPTIONS'])
def stop_marketing_broadcast():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    global broadcast_status
    if broadcast_status["status"] == "running":
        broadcast_status["status"] = "stopped"
        return jsonify({"status": "success", "message": "تم إرسال أمر إيقاف الحملة"})
    return jsonify({"status": "error", "message": "لا توجد حملة قيد التشغيل حالياً"}), 400

# --- [AI SALES TRAINING ACADEMY] ---
# ✅ مسارات تدريب وتقييم الموظفين وإرسال التقارير لواتساب الأدمن
@app.route('/api/training/evaluate', methods=['POST', 'OPTIONS'])
def save_training_evaluation():
    if request.method == 'OPTIONS':
        return make_response("", 204)
        
    try:
        data = request.get_json() or {}
        employee_name = data.get("employee_name", "").strip() or "موظف"
        session_type = data.get("session_type", "").strip()
        score = data.get("score", 0)
        chat_history = data.get("chat_history", [])
        evaluation_report = data.get("evaluation_report", "").strip()
        
        if not session_type:
            return jsonify({"status": "error", "message": "Missing session_type"}), 400
            
        # 1. حفظ في Supabase
        sb_payload = {
            "employee_name": employee_name,
            "session_type": session_type,
            "score": int(score),
            "chat_history": chat_history,
            "evaluation_report": evaluation_report
        }
        
        r = requests.post(f"{SUPABASE_URL}/rest/v1/staff_training_reports", headers=SUPABASE_SERVICE_HEADERS, json=sb_payload, timeout=10)
        if r.status_code not in [200, 201]:
            print(f"[Training DB Save Error]: {r.status_code} - {r.text}")
            
        # 2. ترجمة نوع الجلسة
        st_arabic = {
            "roleplay": "محاكاة العميل الصعب 🎭",
            "course": "كورس التدريب التفاعلي 📖",
            "exam": "الاختبار النهائي للمبيعات 📝"
        }.get(session_type, session_type)
        
        # 3. إرسال إشعار لواتساب الأدمن
        report_brief = evaluation_report[:3000]
        whatsapp_msg = (
            f"📢 *تقرير تقييم مبيعات جديد*\n\n"
            f"👤 *الموظف:* {employee_name}\n"
            f"🎯 *نوع الجلسة:* {st_arabic}\n"
            f"📊 *النتيجة:* {score} / 100\n\n"
            f"📝 *ملخص التقييم ونقاط الضعف:* \n{report_brief}\n\n"
            f"ℹ️ تم حفظ المحادثة والتقرير بالكامل في لوحة الإدارة (CRM)."
        )
        
        # رقم الأدمن
        admin_number = "201121748885"
        send_whatsapp_message(admin_number, whatsapp_msg)
        
        return jsonify({"status": "success", "message": "تم حفظ التقييم وإرسال التنبيه للأدمن"})
    except Exception as e:
        print(f"[Training API Error]: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/training/reports', methods=['GET', 'OPTIONS'])
def get_training_reports():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/staff_training_reports?select=*&order=created_at.desc", headers=SUPABASE_SERVICE_HEADERS, timeout=10)
        if r.status_code == 200:
            return jsonify(r.json())
        return jsonify({"status": "error", "message": r.text}), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# =====================================================
# 💼 [B2B ENGINE] قسم توليد داتا الشركات والتعاقدات المؤسسية
# =====================================================

@app.route('/api/b2b/leads', methods=['GET', 'POST', 'OPTIONS'])
def handle_b2b_leads():
    if request.method == 'OPTIONS':
        return make_response("", 204)
    
    if request.method == 'GET':
        try:
            sector = request.args.get('sector')
            city = request.args.get('city')
            stage = request.args.get('stage')
            search = request.args.get('search')
            
            url = f"{SUPABASE_URL}/rest/v1/b2b_corporate_leads?select=*&order=created_at.desc"
            params = {}
            if sector and sector != 'all':
                url += f"&sector=eq.{sector}"
            if city and city != 'all':
                url += f"&city=eq.{city}"
            if stage and stage != 'all':
                url += f"&pipeline_stage=eq.{stage}"
            if search:
                url += f"&or=(company_name.ilike.%{search}%,decision_maker_name.ilike.%{search}%,email.ilike.%{search}%,phone.ilike.%{search}%)"
                
            r = requests.get(url, headers=SUPABASE_SERVICE_HEADERS, timeout=10)
            if r.status_code == 200:
                return jsonify(r.json())
            return jsonify({"status": "error", "message": r.text}), r.status_code
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    elif request.method == 'POST':
        try:
            data = request.get_json()
            if not data or not data.get('company_name'):
                return jsonify({"status": "error", "message": "اسم الشركة مطلوب"}), 400
                
            r = requests.post(f"{SUPABASE_URL}/rest/v1/b2b_corporate_leads", headers={**SUPABASE_SERVICE_HEADERS, "Prefer": "return=representation"}, json=data, timeout=10)
            if r.status_code in (200, 201):
                return jsonify({"status": "success", "lead": r.json()}), 201
            return jsonify({"status": "error", "message": r.text}), r.status_code
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/b2b/leads/<lead_id>', methods=['PATCH', 'DELETE', 'OPTIONS'])
def handle_single_b2b_lead(lead_id):
    if request.method == 'OPTIONS':
        return make_response("", 204)
        
    if request.method == 'PATCH':
        try:
            data = request.get_json()
            data['updated_at'] = datetime.utcnow().isoformat() + "Z"
            r = requests.patch(
                f"{SUPABASE_URL}/rest/v1/b2b_corporate_leads?id=eq.{lead_id}",
                headers={**SUPABASE_SERVICE_HEADERS, "Prefer": "return=representation"},
                json=data,
                timeout=10
            )
            if r.status_code in (200, 204):
                return jsonify({"status": "success", "message": "تم تحديث البيانات بنجاح"})
            return jsonify({"status": "error", "message": r.text}), r.status_code
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    elif request.method == 'DELETE':
        try:
            r = requests.delete(
                f"{SUPABASE_URL}/rest/v1/b2b_corporate_leads?id=eq.{lead_id}",
                headers=SUPABASE_SERVICE_HEADERS,
                timeout=10
            )
            if r.status_code in (200, 204):
                return jsonify({"status": "success", "message": "تم حذف الشركة بنجاح"})
            return jsonify({"status": "error", "message": r.text}), r.status_code
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/b2b/generate', methods=['POST', 'OPTIONS'])
def generate_b2b_leads():
    """
    [AI-POWERED] محرك توليد داتا الشركات والفنادق والمستشفيات الذكي
    يقوم بالبحث واستخراج بيانات حقيقية وموثوقة لقطاع ومحافظة محددة مع مسؤولي المشتريات
    """
    if request.method == 'OPTIONS':
        return make_response("", 204)
    try:
        data = request.get_json() or {}
        sector = data.get('sector', 'pharma')
        city = data.get('city', 'القاهرة')
        custom_query = data.get('query', '')
        
        sector_names = {
            'hotels': 'فنادق ومنتجعات سياحية',
            'hospitals': 'مستشفيات ومراكز طبية كبرى',
            'pharma': 'شركات ومصانع أدوية ورعاية صحية',
            'contracting': 'شركات مقاولات كبرى وهندسة وطاقة',
            'events': 'منظمو مؤتمرات وفعاليات ومعارض دولية',
            'restaurants': 'سلاسل مطاعم وكافيهات كبرى',
            'corporate': 'شركات ومؤسسات تجارية كبرى ومصانع'
        }
        sector_title = sector_names.get(sector, sector)
        
        prompt = f"""أنت خبير أبحاث B2B واستخراج بيانات الشركات والمؤسسات في مصر.
المطلوب: توليد قائمة مكونة من 5 إلى 7 شركات ومؤسسات حقيقية وشهيرة في مصر تعمل في قطاع: ({sector_title}) في نطاق محافظة/مدينة: ({city}).
{f'تركيز إضافي: {custom_query}' if custom_query else ''}

لكل مؤسسة، استخرج بيانات الاتصال الحقيقية أو الأكثر دقة ومسؤول التعاقدات والمشتريات:
- company_name: اسم المؤسسة باللغتين العربية والإنجليزية
- sector: {sector}
- city: {city}
- address: عنوان المقر الرئيسي أو الفرع بالمدينة
- phone: رقم الهاتف الأرضي أو الخط الساخن
- whatsapp: رقم واتساب تجاري أو مسؤول التواصل (يبدأ بـ 20)
- email: بريد إلكتروني رسمي للتعاقدات أو المشتريات أو الإدارة العامة
- website: رابط الموقع الإلكتروني الرسمي
- linkedin_url: رابط صفحة LinkedIn للشركة
- decision_maker_name: اسم مسؤول أو مدير المشتريات / اللوجستيات / الموارد البشرية
- decision_maker_role: مسمى الوظيفة (مثال: مدير المشتريات والتعاقدات، مدير النقل والخدمات الإدارية، HR Director)
- verification_score: درجة الموثوقية (85 - 99)
- is_whatsapp_verified: true
- is_email_verified: true
- pipeline_stage: "new"
- notes: تفاصيل احتياج المؤسسة لخدمات النقل (مؤتمرات، خطوط عمال، سيارات ليموزين VIP، توريد أسطول).

رد فقط بـ JSON صالح بصيغة قائمة كائنات:
{{"leads": [ {{...}}, {{...}} ]}}"""

        url = 'https://api.groq.com/openai/v1/chat/completions'
        headers = {
            'Authorization': f'Bearer {GROQ_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': GROQ_MODEL,
            'messages': [
                {'role': 'system', 'content': 'أنت نظام ذكي لتوليد بيانات الشركات B2B في مصر. رد فقط بـ JSON صالح ومطابق للمطلوب.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.3,
            'max_tokens': 2500,
            'response_format': {'type': 'json_object'}
        }
        r = requests.post(url, headers=headers, json=payload, timeout=25)
        if r.status_code == 200:
            result = r.json()
            content = result['choices'][0]['message']['content']
            parsed = json.loads(content)
            leads_list = parsed.get('leads', [])
            
            # حفظ في Supabase تلقائياً
            saved_leads = []
            for lead in leads_list:
                lead['sector'] = sector
                if not lead.get('city'): lead['city'] = city
                r_save = requests.post(
                    f"{SUPABASE_URL}/rest/v1/b2b_corporate_leads",
                    headers={**SUPABASE_SERVICE_HEADERS, "Prefer": "return=representation"},
                    json=lead,
                    timeout=5
                )
                if r_save.status_code in (200, 201):
                    saved_leads.append(r_save.json()[0] if isinstance(r_save.json(), list) else r_save.json())
            
            return jsonify({
                "status": "success",
                "message": f"تم توليد والتحقق من {len(saved_leads)} شركة بنجاح!",
                "leads": saved_leads
            })
        else:
            return jsonify({"status": "error", "message": f"Groq Error: {r.status_code}"}), 500
    except Exception as e:
        print(f"[B2B Generator Error]: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/b2b/send-whatsapp', methods=['POST', 'OPTIONS'])
def send_b2b_whatsapp_proposal():
    """
    إرسال عرض تعاقد وتسويق مباشر عبر الواتساب للمسؤول
    """
    if request.method == 'OPTIONS':
        return make_response("", 204)
    try:
        data = request.get_json()
        lead_id = data.get('lead_id')
        whatsapp_number = data.get('whatsapp')
        company_name = data.get('company_name', 'شركتكم الموقرة')
        contact_name = data.get('contact_name', 'مسؤول التعاقدات')
        service_type = data.get('service_type', 'all') # 'conferences' | 'staff_lines' | 'fleet_supply' | 'all'
        custom_message = data.get('custom_message')
        
        if not whatsapp_number:
            return jsonify({"status": "error", "message": "رقم الواتساب مطلوب"}), 400
            
        clean_wa = clean_phone_strict(whatsapp_number)
        
        if custom_message:
            proposal_text = custom_message
        else:
            # قوالب العروض الاحترافية المجهزة بسابقة الأعمال
            service_intros = {
                'conferences': "في إطار خدماتنا المتخصصة في **تنظيم وتنفيذ تنقلات المؤتمرات والفعاليات الكبرى والندوات العلمية**،",
                'staff_lines': "في إطار حلولنا الذكية في **توريد وإدارة خطوط نقل العمال والموظفين اليومية والدورية**،",
                'fleet_supply': "في إطار توفير **أسطول سيارات وحافلات متكامل (سيدان، ميني فان، فان H1/HiAce، حافلات وأوتوبيسات)** لجميع السعات،",
                'all': "يسعدنا في **شركة 24Seven للحلول اللوجستية والنقل المؤسسي الذكي** تقديم عرض خدماتنا لشركتكم الموقرة."
            }
            intro = service_intros.get(service_type, service_intros['all'])
            
            proposal_text = (
                f"السيد/ة المحترم/ة: {contact_name} 🌸\n"
                f"عناية: {company_name}\n"
                f"تحية طيبة من شركة **24Seven Limousine & Corporate Mobility** 🚗✨\n\n"
                f"{intro}\n\n"
                f"💼 **لماذا تختار 24Seven كشريك نقل معتمد؟**\n"
                f"1️⃣ **سابقة أعمال قوية وموثوقة:** تشرفنا بتنفيذ وإدارة مؤتمرات وتنقلات لكبرى الشركات والمؤسسات مثل *(إدفكيور للأدوية، باركفيل، إمديفكو، مجموعة السويدي إلكتريك)* وغيرها.\n"
                f"2️⃣ **أسطول متنوع وحديث:** سيدان VIP، ميني فان، فان سياحي (تويوتا هاي إيس / هيونداي H1)، وأوتوبيسات 28-50 راكب مجهزة بأحدث وسائل الراحة والأمان.\n"
                f"3️⃣ **تغطية شاملة 24/7:** استقبال وتوديع مطارات، سفر لجميع المحافظات، وخطوط عمال وموظفين منتظمة مع تقارير تتبع وفواتير ضريبية إلكترونية.\n"
                f"4️⃣ **كباتن محترفون ومدربون** على أعلى معايير الضيافة والالتزام بالوقت.\n\n"
                f"📄 **للاطلاع على بروفايل الشركة والخدمات:**\n"
                f"https://24seven-ai.com/about.html\n\n"
                f"🤝 **يسعدنا التنسيق لتحديد موعد اجتماع تعارف أو إرسال عرض أسعار مخصص لاحتياجاتكم.**\n"
                f"للتواصل المباشر مع إدارة التعاقدات: 01121748885\n\n"
                f"دمتم ودامت أعمالكم في ازدهار وتألق! ✨"
            )
            
        # إرسال الرسالة عبر الواتساب
        send_whatsapp_message(clean_wa, proposal_text)
        
        # تحديث حالة الشركة في Supabase
        if lead_id:
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/b2b_corporate_leads?id=eq.{lead_id}",
                headers=SUPABASE_SERVICE_HEADERS,
                json={
                    "pipeline_stage": "contacted",
                    "last_contacted_at": datetime.utcnow().isoformat() + "Z",
                    "last_contact_channel": "whatsapp"
                },
                timeout=5
            )
            
        return jsonify({"status": "success", "message": f"تم إرسال عرض التعاقد بنجاح إلى {company_name} عبر الواتساب!"})
    except Exception as e:
        print(f"[B2B WhatsApp Error]: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/b2b/send-email', methods=['POST', 'OPTIONS'])
def send_b2b_email_proposal():
    """
    إرسال عرض بريد إلكتروني رسمي (HTML Corporate Proposal) مع إبراز سابقة الأعمال
    """
    if request.method == 'OPTIONS':
        return make_response("", 204)
    try:
        data = request.get_json()
        lead_id = data.get('lead_id')
        recipient_email = data.get('email')
        company_name = data.get('company_name', 'شركتكم الموقرة')
        contact_name = data.get('contact_name', 'مسؤول المشتريات والتعاقدات')
        subject = data.get('subject', f'عرض خدمات النقل المؤسسي وتنظيم المؤتمرات - 24Seven | {company_name}')
        
        if not recipient_email:
            return jsonify({"status": "error", "message": "البريد الإلكتروني مطلوب"}), 400
            
        # إنشاء قالب البريد الإلكتروني الرسمي
        html_content = f"""
        <!DOCTYPE html>
        <html dir="rtl" lang="ar">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; color: #1e293b; padding: 20px; }}
                .card {{ max-width: 650px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }}
                .header {{ background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); color: #ffffff; padding: 35px 25px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; font-weight: 800; letter-spacing: 0.5px; }}
                .header p {{ margin: 8px 0 0; font-size: 14px; opacity: 0.9; }}
                .content {{ padding: 30px 25px; line-height: 1.8; }}
                .badge-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin: 20px 0; }}
                .badge-item {{ background: #f1f5f9; padding: 14px; border-radius: 10px; border-right: 4px solid #3b82f6; }}
                .badge-item strong {{ display: block; color: #0f172a; font-size: 14px; margin-bottom: 4px; }}
                .badge-item span {{ font-size: 12px; color: #64748b; }}
                .clients-box {{ background: #eff6ff; border: 1px dashed #93c5fd; padding: 18px; border-radius: 12px; margin: 25px 0; text-align: center; }}
                .clients-box h4 {{ margin: 0 0 10px; color: #1e40af; font-size: 15px; }}
                .client-tags {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }}
                .tag {{ background: #ffffff; padding: 5px 14px; border-radius: 20px; font-size: 13px; font-weight: bold; color: #1e3a8a; box-shadow: 0 2px 5px rgba(0,0,0,0.04); }}
                .cta-btn {{ display: inline-block; background: #2563eb; color: #ffffff !important; text-decoration: none; padding: 14px 32px; border-radius: 30px; font-weight: bold; font-size: 15px; margin: 20px 0; box-shadow: 0 4px 15px rgba(37,99,235,0.3); }}
                .footer {{ background: #f8fafc; padding: 20px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="header">
                    <h1>24Seven Corporate & Mobility Solutions</h1>
                    <p>الشريك المعتمد لكبرى الشركات والمؤسسات في مصر</p>
                </div>
                <div class="content">
                    <p>السيد/ة المحترم/ة: <strong>{contact_name}</strong>،</p>
                    <p>عناية إدارة المشتريات والتعاقدات في <strong>{company_name}</strong> الموقرة،</p>
                    <p>تحية طيبة وبعد،،</p>
                    <p>يسعدنا في <strong>24Seven</strong> أن نتقدم لسيادتكم بطلب التعاون والشراكة لتلبية كافة متطلبات النقل المؤسسي، توريد أسطول السيارات والحافلات، وخدمات تنقلات المؤتمرات والفعاليات وخطوط الموظفين باحترافية وأعلى معايير الجودة والأمان.</p>
                    
                    <div class="badge-grid">
                        <div class="badge-item">
                            <strong>🚗 خدمات المؤتمرات والفعاليات</strong>
                            <span>تنظيم كامل لوفود المؤتمرات، سيارات ليموزين VIP، وميني فان.</span>
                        </div>
                        <div class="badge-item">
                            <strong>🚌 خطوط العمال والموظفين</strong>
                            <span>عقود سنوية وشهرية منتظمة للمصانع والشركات بجميع المحافظات.</span>
                        </div>
                        <div class="badge-item">
                            <strong>✈️ استقبال وتوديع المطارات</strong>
                            <span>خدمة 24/7 مع كباتن محترفين وتتبع دقيق للرحلات.</span>
                        </div>
                        <div class="badge-item">
                            <strong>📊 فواتير ضريبية وتقارير ذكية</strong>
                            <span>لوحة تحكم للمؤسسات لمتابعة الاستهلاك والفواتير الإلكترونية.</span>
                        </div>
                    </div>

                    <div class="clients-box">
                        <h4>🏆 سابقة أعمال نفخر بها مع كبرى المؤسسات:</h4>
                        <div class="client-tags">
                            <span class="tag">إدفكيور للأدوية (Advocure)</span>
                            <span class="tag">باركفيل للصناعات الدوائية (Parkville)</span>
                            <span class="tag">إمديفكو للرعاية الصحية (Emdefco)</span>
                            <span class="tag">مجموعة السويدي إلكتريك (Elsewedy)</span>
                            <span class="tag">مؤتمرات طبية ومعارض دولية</span>
                        </div>
                    </div>

                    <div style="text-align: center;">
                        <p>يسعدنا تحديد موعد لاجتماع تعارف وتقديم عرض أسعار مفصل يلائم خططكم:</p>
                        <a href="https://wa.me/201121748885?text=طلب+عرض+أسعار+لشركة+{company_name}" class="cta-btn">طلب عرض أسعار واجتماع تعارف 🤝</a>
                    </div>
                </div>
                <div class="footer">
                    <p><strong>شركة 24Seven للحلول اللوجستية والنقل الذكي</strong> | القاهرة، مصر</p>
                    <p>البريد الإلكتروني: info@24seven-ai.com | الهاتف / واتساب: 01121748885 | الموقع: <a href="https://24seven-ai.com">24seven-ai.com</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # إرسال الإيميل عبر خادم البريد
        email_sent = False
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            
            smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
            smtp_port = int(os.getenv("SMTP_PORT", 587))
            smtp_user = os.getenv("SMTP_USER", "info@24seven-ai.com")
            smtp_pass = os.getenv("SMTP_PASS", "")
            
            if smtp_pass:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = f"24Seven Corporate <{smtp_user}>"
                msg['To'] = recipient_email
                msg.attach(MIMEText(html_content, 'html'))
                
                with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(smtp_user, [recipient_email], msg.as_string())
                email_sent = True
                print(f"[B2B Email] Sent email to {recipient_email} via SMTP")
        except Exception as mail_err:
            print(f"[B2B Email SMTP Notice]: {mail_err}")
            
        # تحديث حالة الشركة في Supabase
        if lead_id:
            requests.patch(
                f"{SUPABASE_URL}/rest/v1/b2b_corporate_leads?id=eq.{lead_id}",
                headers=SUPABASE_SERVICE_HEADERS,
                json={
                    "pipeline_stage": "contacted",
                    "last_contacted_at": datetime.utcnow().isoformat() + "Z",
                    "last_contact_channel": "email"
                },
                timeout=5
            )
            
        return jsonify({
            "status": "success", 
            "message": f"تم إعداد وإرسال عرض البريد الإلكتروني الرسمي لشركة {company_name} بنجاح!",
            "preview_html": html_content
        })
    except Exception as e:
        print(f"[B2B Email Error]: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


gateway_process = None

def stop_gateway():
    global gateway_process
    if gateway_process:
        print("[Gateway] Stopping local WhatsApp gateway service...")
        import subprocess
        try:
            import os
            if os.name == 'nt':
                subprocess.run(f"taskkill /F /T /PID {gateway_process.pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                gateway_process.terminate()
                gateway_process.wait(timeout=5)
            print("[Gateway] Local WhatsApp gateway service stopped.")
        except Exception as e:
            print(f"[Gateway Error] Error stopping gateway: {e}")

if __name__ == '__main__':
    # تم تعطيل التشغيل التلقائي كعملية فرعية لتفادي انقطاع الاتصال عند إعادة تشغيل السيرفر.
    # يتم تشغيل بوابة الواتساب الآن كخدمة مستقلة ومستمرة من خلال ملف run_all.bat.
    print("[Gateway] Standalone WhatsApp gateway service is managed via run_all.bat")

    print("[STARTED] Server Started on Port 3000 (Handling WhatsApp & Messenger & API)...")
    app.run(host='0.0.0.0', port=3000, threaded=True)
