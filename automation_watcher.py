import sys
sys.stdout.reconfigure(encoding='utf-8')
import time
import traceback
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import os
import re
from datetime import datetime, timedelta
import random


import json

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sent_messages_cache.json")

def load_sent_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}")
    return {}

def save_sent_cache(cache):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving cache: {e}")

# =====================================================
# 📂 إعدادات جوجل شيت و Supabase
# =====================================================
SUPABASE_URL = "https://khskudtxbypohvnreloi.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjMxMjAyOSwiZXhwIjoyMTAxODg4MDI5fQ.uyCTVGkoeoz4xB3r2muV_fLiI62QIw-65g2nVeIb62w"
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

import ssl
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 🛡️ إعداد المحول الشبكي المقاوم للقطع وانهيار SSL/TLS
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

def create_resilient_session():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504], raise_on_status=False)
    adapter = ResilientTLSAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

http_session = create_resilient_session()

# =====================================================
# ⚙️ إعدادات النظام (واتساب الربط)
# =====================================================
SHEET_NAME = "امر حجز عميل"
TASK_INSTANCE_PHONE = "201121748885" # الرقم المخصص للمهام والـ Automation
CHAT_INSTANCE_PHONE = "201121747555" # الرقم المخصص للدردشة والموديتور

_instance_cache = {}

def get_whatsapp_instance(phone_number):
    if phone_number in _instance_cache:
        return _instance_cache[phone_number]
        
    for attempt in range(3):
        try:
            url = f"{SUPABASE_URL}/rest/v1/whatsapp_instances?phone=eq.{phone_number}"
            res = http_session.get(url, headers=SUPABASE_HEADERS, timeout=5)
            if res.ok and len(res.json()) > 0:
                inst = res.json()[0]
                _instance_cache[phone_number] = inst
                return inst
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                print(f"⚠️ يتعذر الاتصال بالسحابة لاستجلاب الإنستانس لـ {phone_number}: {e}")
                
    # Fallback تلقائي للبوابة المحلية لمنع توقف الخدمة أبداً
    print(f"🔄 استخدام البوابة المحلية الافتراضية للرقم {phone_number} لاستمرار الإرسال...")
    fallback_inst = {
        "id": "692921bb-a5df-451d-8527-e1ee55a736f4",
        "phone": phone_number,
        "provider": "local",
        "api_url": "http://localhost:3001"
    }
    _instance_cache[phone_number] = fallback_inst
    return fallback_inst

# =====================================================
# 🛠️ دوال التنظيف (الحل الجذري للمشكلة #132018)
# =====================================================

def clean_param(text):
    """
    تقوم هذه الدالة بإزالة أي نزول للسطر (Enter) 
    أو مسافات زائدة لأن واتساب يرفضها
    """
    if not text: return " "
    text = str(text)
    # استبدال Enter بشرطة
    text = text.replace('\n', ' - ').replace('\r', ' ').replace('\t', ' ')
    # إزالة المسافات المتكررة
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def arabic_to_latin_digits(text):
    """تحويل الأرقام العربية/الشرقية (٠١٢٣٤٥٦٧٨٩) إلى أرقام لاتينية (0123456789)"""
    arabic_digits = '٠١٢٣٤٥٦٧٨٩'
    latin_digits  = '0123456789'
    table = str.maketrans(arabic_digits, latin_digits)
    return str(text).translate(table)

def clean_phone(phone):
    """تجهيز الرقم ليقبل الإرسال - يدعم الأرقام المصرية والدولية"""
    if not phone: return None
    
    # ✅ الخطوة الأولى: تحويل الأرقام العربية إلى لاتينية
    phone = arabic_to_latin_digits(phone)
    
    # تنظيف من أي مسافات أو رموز
    clean = re.sub(r'\D', '', str(phone))
    
    # إزالة الأصفار في البداية تماماً
    while clean.startswith("0"):
        clean = clean[1:]
        
    # منطق مرن للأرقام المصرية:
    # أي رقم يبدأ بـ 1 وطوله 9 أو 10 (بعد حذف الصفر) يحتاج 20
    if clean.startswith("1") and (len(clean) == 9 or len(clean) == 10):
        return "20" + clean
    # إذا بدأ بـ 201 وطوله كامل (11-12 رقم) نتركه كما هو
    if clean.startswith("201") and (len(clean) == 11 or len(clean) == 12):
        return clean
        
    # إعادة الرقم كما هو إذا كان طوله مقبول (دولي)
    return clean if len(clean) >= 9 else None

def parse_smart_date(date_str):
    if not date_str: return None
    date_str = str(date_str).strip().split(' ')[0]
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    return None

_cached_client = None
_cached_spreadsheet = None

def get_sheet():
    global _cached_client, _cached_spreadsheet
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    for attempt in range(3):
        try:
            if _cached_client is None:
                creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
                _cached_client = gspread.authorize(creds)
            if _cached_spreadsheet is None:
                _cached_spreadsheet = _cached_client.open_by_url('https://docs.google.com/spreadsheets/d/1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4/edit')
            return _cached_spreadsheet.worksheet(SHEET_NAME)
        except Exception as e:
            # Clear cache on error to retry fresh authorization/open next attempt
            _cached_client = None
            _cached_spreadsheet = None
            if attempt < 2:
                time.sleep(3)
            else:
                raise e

def insert_message_to_supabase(sender_id, msg_text, whatsapp_instance_id=None):
    """إدراج الرسالة المرسلة في Supabase للظهور في لوحة المودريتور"""
    url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages"
    data = {
        "channel": "whatsapp",
        "sender_id": str(sender_id),
        "sender_name": "Automation Bot",
        "message_text": msg_text,
        "is_from_admin": True,
        "read_by_admin": True
    }
    if whatsapp_instance_id:
        data["whatsapp_instance_id"] = whatsapp_instance_id
    try:
        http_session.post(url, headers=SUPABASE_HEADERS, json=data, timeout=5)
    except Exception as e:
        print(f"Supabase Insert Error: {e}")

def send_linked_whatsapp(to, message_text, instance=None):
    if not to or not message_text: return False
    
    # الحصول على الإنستانس المخصص للمهام
    if not instance:
        instance = get_whatsapp_instance(TASK_INSTANCE_PHONE)
    
    if not instance:
        print(f"❌ لم يتم العثور على الواتساب المربوط برقم {TASK_INSTANCE_PHONE}")
        return False
        
    try:
        base_url = (instance.get('api_url') or 'https://api.ultramsg.com').rstrip('/')
        inst_id = instance.get('instance_id')
        token = instance.get('token')
        provider = instance.get('provider', 'local')
        
        if provider == 'local':
            send_url = f"{base_url}/instance/{instance.get('id')}/send"
            payload = {
                "to": str(to).replace('+', ''),
                "message": message_text
            }
            r = http_session.post(send_url, json=payload, timeout=10)
        else:
            send_url = f"{base_url}/{inst_id}/messages/chat"
            payload = {
                "token": token,
                "to": str(to).replace('+', ''),
                "body": message_text
            }
            r = http_session.post(send_url, data=payload, timeout=10)
        
        if r.status_code == 200:
            print(f"✅ Sent message to {to} via {instance.get('phone')}")
            insert_message_to_supabase(to, message_text, whatsapp_instance_id=instance.get('id'))
            # إضافة حماية لتجنب الحظر (تأخير عشوائي بسيط لمحاكاة البشر)
            time.sleep(random.randint(4, 8))
            return True
            
        print(f"❌ Error sending to {to}: {r.text}")
        return False
    except Exception as e:
        err_str = str(e)
        if "10061" in err_str or "ConnectionRefused" in err_str:
            print("⚠️ [تنبيه] بوابة الواتساب المحلية مغلقة أو تعيد الاتصال حالياً...")
        else:
            print(f"❌ خطأ أثناء إرسال الواتساب: {err_str[:120]}")
        return False

# =====================================================
# 🚀 المحرك الرئيسي
# =====================================================
print("\n" + "="*50)
print("🚀 خدمة الواتساب (الإصدار المحسن)")
print("   ✅ تم حل مشكلة Enter والمسافات")
print("="*50 + "\n")


while True:
    try:
        sheet = get_sheet()
        rows = sheet.get_all_values()
        sent_cache = load_sent_cache()
        
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        today = datetime.now().date()
        
        # الحصول على الإنستانس المخصص للمهام مرة واحدة لكل دورة فحص
        task_instance = get_whatsapp_instance(TASK_INSTANCE_PHONE)
        if not task_instance:
            print(f"⚠️ تحذير: لم يتم العثور على الرقم المخصص للمهام {TASK_INSTANCE_PHONE}، سنحاول لاحقاً.")
        
        if len(rows) > 1:
            for i, row in enumerate(rows[1:]):
                real_idx = i + 2
                while len(row) < 45: row.append("") 

                # قراءة البيانات الأساسية
                raw_date   = row[1]
                trip_time  = row[2]
                cust_name  = row[3]
                cust_phone = clean_phone(row[4])
                pickup     = row[6]
                dropoff    = row[7]
                car_type   = row[10]
                price      = row[12]
                notes      = row[14]
                driver_name  = row[21]
                driver_phone = clean_phone(row[22])

                # ======================================================
                # قراءة حالات الإرسال (الأعمدة Y=25, Z=26, AA=27, AB=28)
                # col 25 (index 24) = msg_driver_status
                # col 26 (index 25) = msg_feedback_status
                # col 27 (index 26) = msg_confirm_status  (تذكير قبل يوم)
                # col 28 (index 27) = msg_booking_status  (تأكيد الحجز الفوري ← جديد)
                # col 29 (index 28) = location_url
                # ======================================================
                msg_driver_status  = row[24].strip()
                msg_feedback_status = row[25].strip()
                msg_confirm_status  = row[26].strip()
                msg_booking_status  = row[23].strip()   # ← تم الإصلاح: يقرأ من العمود 24 المخصص لتأكيد الحجز الفوري
                location_url = str(row[28]).strip()

                t_date = parse_smart_date(raw_date)

                # -------------------------------------------------------
                # تحديد حالة الرحلة (هل انتهت فعلاً؟)
                # نعتبرها انتهت فقط إذا:
                #   أ) وُجد نص "تم"/"انهاء" في أعمدة الإنهاء (34-38)
                #   ب) تاريخها أقل من اليوم + سائق معيّن + العميل أكّد
                # -------------------------------------------------------
                is_done_manual = False
                for col_idx in range(34, 39):
                    if "تم" in str(row[col_idx]) or "انهاء" in str(row[col_idx]):
                        is_done_manual = True
                        break

                # ✅ إصلاح: is_past_trip الآن يشترط وجود سائق + تأكيد عميل
                driver_was_assigned = driver_name.strip() != ""
                client_had_confirmed = msg_confirm_status != "" or msg_booking_status != ""
                is_past_trip = is_done_manual or (
                    t_date and t_date < today
                    and driver_was_assigned
                    and client_had_confirmed
                )

                # تخطي الصفوف بدون تاريخ أو بدون رقم عميل
                if not cust_phone or not t_date:
                    continue

                # ✅ فحص الإلغاء: تجنب إرسال أي رسائل للعملاء الذين ألغوا حجزهم
                client_decision = row[27].strip()
                trip_general_status = row[35].strip()
                
                is_cancelled = (
                    "ملغي" in msg_confirm_status or "الغاء" in msg_confirm_status or "لغي" in msg_confirm_status or
                    "ملغي" in msg_booking_status or "الغاء" in msg_booking_status or "لغي" in msg_booking_status or
                    "ملغي" in client_decision or "الغاء" in client_decision or "لغي" in client_decision or "رفض" in client_decision or
                    "ملغي" in trip_general_status or "cancel" in client_decision.lower() or "cancel" in trip_general_status.lower()
                )
                
                if is_cancelled:
                    # تخطي الحجوزات الملغية تماماً
                    continue

                # =======================================================
                # 0️⃣  تأكيد الحجز الفوري (رسالة فورية لما يدخل الموظف الحجز)
                # الشرط: الرحلة في المستقبل + التأكيد الفوري لم يُرسل بعد
                # =======================================================
                is_future_trip = t_date >= today
                cache_key_booking = f"{str(t_date)}_{cust_phone}_booking"
                if is_future_trip and msg_booking_status == "" and not sent_cache.get(cache_key_booking):
                    print(f"📋 صف {real_idx}: حجز جديد ({cust_name}) — إرسال تأكيد فوري...")

                    booking_msg = (
                        f"أهلاً بك أستاذ {cust_name} 🌟\n"
                        f"تم تسجيل حجزك مع 24Seven بنجاح! ✅\n\n"
                        f"📅 تاريخ الرحلة: {str(t_date)}\n"
                        f"⏰ وقت التحرك: {str(trip_time)}\n"
                        f"📍 من: {pickup}\n"
                        f"🏁 إلى: {dropoff}\n"
                        f"🚘 نوع السيارة: {car_type}\n"
                        f"💵 التكلفة: {price}\n"
                        f"📝 ملاحظات: {notes or 'لا يوجد'}\n\n"
                        f"سيتم إرسال تفاصيل الكابتن قريباً.\n"
                        f"شكراً لاختيارك 24Seven! ✨"
                    )

                    # ✅ إصلاح مكرر: سجّل أولاً قبل الإرسال لمنع التكرار
                    sheet.update_cell(real_idx, 24, "جاري الإرسال...")
                    time.sleep(1)
                    if send_linked_whatsapp(cust_phone, booking_msg, task_instance):
                        sheet.update_cell(real_idx, 24, "تم إرسال تأكيد الحجز ✅")
                        sent_cache[cache_key_booking] = True
                        save_sent_cache(sent_cache)
                    else:
                        sheet.update_cell(real_idx, 24, "")
                    time.sleep(3)

                # =======================================================
                # 1️⃣  تذكير قبل الرحلة بيوم (تأكيد / إلغاء)
                # الشرط: الرحلة غداً أو اليوم + التذكير لم يُرسل بعد
                # =======================================================
                is_remind_day = (t_date == tomorrow or t_date == today)
                cache_key_reminder = f"{str(t_date)}_{cust_phone}_reminder"
                if is_remind_day and msg_confirm_status == "" and not sent_cache.get(cache_key_reminder):
                    print(f"🔔 صف {real_idx}: إرسال تذكير قبل الرحلة لـ ({cust_name})...")

                    remind_msg = (
                        f"أهلاً أستاذ {cust_name} 👋\n"
                        f"تذكير: رحلتك مع 24Seven {'غداً' if t_date == tomorrow else 'اليوم'}!\n\n"
                        f"📅 التاريخ: {str(t_date)}\n"
                        f"⏰ الوقت: {str(trip_time)}\n"
                        f"📍 من: {pickup}\n"
                        f"🏁 إلى: {dropoff}\n"
                        f"💵 التكلفة: {price}\n\n"
                        f"📌 يرجى الرد بـ (تأكيد) لتأكيد الحجز، أو بـ (إلغاء) لرفض الطلب."
                    )

                    # ✅ إصلاح مكرر: سجّل أولاً قبل الإرسال
                    sheet.update_cell(real_idx, 27, "جاري الإرسال...")
                    time.sleep(1)
                    if send_linked_whatsapp(cust_phone, remind_msg, task_instance):
                        sheet.update_cell(real_idx, 27, "تم إرسال التذكير ✅")
                        sent_cache[cache_key_reminder] = True
                        save_sent_cache(sent_cache)
                    else:
                        sheet.update_cell(real_idx, 27, "")
                    time.sleep(3)

                # =======================================================
                # 2️⃣  إبلاغ السائق والعميل (عند تعيين سائق)
                # ✅ إصلاح: يُرسل فقط بعد أن يكون العميل قد تلقى تأكيداً
                # =======================================================
                status_to_check = msg_driver_status
                if "(شامل)" in status_to_check:
                    status_to_check = ""

                booking_was_sent = msg_booking_status != "" and "فشل" not in msg_booking_status
                is_invalid_driver = (
                    not driver_name or
                    len(driver_name.strip()) < 3 or
                    "تست" in driver_name or
                    "test" in driver_name.lower() or
                    "سائق" == driver_name.strip() or
                    "كابتن" == driver_name.strip() or
                    not driver_phone or
                    len(driver_phone.strip()) < 8 or
                    "0000000" in driver_phone or
                    "01121747555" in driver_phone
                )

                # ✅ فحص تعيين الكابتن: وجود كابتن حقيقي برقم صحيح ولم يتم إبلاغ الطرفين بعد
                cache_key_driver = f"{str(t_date)}_{cust_phone}_{driver_phone}_driver"
                if (driver_name.strip() != ""
                        and not is_invalid_driver
                        and status_to_check == ""
                        and not is_past_trip
                        and not sent_cache.get(cache_key_driver)):

                    print(f"🚕 صف {real_idx}: تم تعيين كابتن حقيقي ({driver_name} - {driver_phone}) لـ ({cust_name})...")

                    # رسالة العميل — بيانات الكابتن
                    client_msg = (
                        f"أهلاً أستاذ {cust_name} 👋\n"
                        f"تم تعيين الكابتن لرحلتك بنجاح! 🚕\n\n"
                        f"👤 الكابتن: {driver_name}\n"
                        f"🚘 السيارة: {car_type}\n\n"
                        f"🔗 لمتابعة الرحلة والتواصل مع الكابتن:\n"
                        f"https://24seven-ai.com/limousine.html\n\n"
                        f"24Seven تتمنى لك رحلة سعيدة! ✨"
                    )

                    # ✅ إصلاح مكرر: سجّل أولاً
                    sheet.update_cell(real_idx, 25, "جاري إبلاغ العميل...")
                    time.sleep(1)
                    s1 = send_linked_whatsapp(cust_phone, client_msg, task_instance)
                    if s1: time.sleep(3)

                    # رسالة السائق — أمر الشغل
                    s2 = False
                    if driver_phone:
                        notes_content = f"{notes} | ⚠️ عميل VIP"
                        if location_url and len(location_url) > 5:
                            notes_content += f" | 📍 {location_url}"

                        driver_msg = (
                            f"أمر شغل جديد 🚨\n"
                            f"👤 العميل: {cust_name}\n"
                            f"📅 التاريخ: {str(raw_date)}\n"
                            f"⏰ الوقت: {str(trip_time)}\n"
                            f"📍 التحرك: {pickup}\n"
                            f"🏁 الوصول: {dropoff}\n"
                            f"💵 التحصيل: {price}\n"
                            f"📝 ملاحظات: {notes_content}\n\n"
                            f"🔗 لمتابعة الرحلة:\n"
                            f"https://24seven-ai.com/driver.html"
                        )
                        s2 = send_linked_whatsapp(driver_phone, driver_msg, task_instance)
                        if s2: time.sleep(3)
                    else:
                        print(f"⚠️ هاتف السائق '{row[22]}' مفقود (صف {real_idx})")

                    # تحديث الحالة النهائية
                    if s1 and s2:
                        sheet.update_cell(real_idx, 25, "تم إبلاغ الطرفين ✅")
                        sent_cache[cache_key_driver] = True
                        save_sent_cache(sent_cache)
                    elif s1:
                        sheet.update_cell(real_idx, 25, "تم إبلاغ العميل فقط ✅")
                        sent_cache[cache_key_driver] = True
                        save_sent_cache(sent_cache)
                    elif s2:
                        sheet.update_cell(real_idx, 25, "تم إبلاغ السائق فقط ✅")
                    else:
                        sheet.update_cell(real_idx, 25, "")

                # =======================================================
                # 3️⃣  الفيدباك (بعد انتهاء الرحلة فعلاً)
                # ✅ إصلاح: لا نرسل إلا إذا:
                #   - تم التعيين اليدوي (تم/انهاء) أو
                #   - الرحلة مضت + سائق معيّن + العميل تلقى تأكيداً
                # =======================================================
                should_send_feedback = False
                yesterday = today - timedelta(days=1)
                if is_done_manual:
                    if t_date and t_date >= yesterday:
                        should_send_feedback = True
                elif (t_date and yesterday <= t_date < today
                      and driver_was_assigned
                      and client_had_confirmed):
                    should_send_feedback = True

                cache_key_feedback = f"{str(t_date)}_{cust_phone}_feedback"
                if should_send_feedback and msg_feedback_status == "" and not sent_cache.get(cache_key_feedback):
                    print(f"⭐ صف {real_idx}: إرسال طلب التقييم لـ ({cust_name})...")

                    fb_msg = (
                        f"أهلاً بك أستاذ {cust_name} 🌟\n"
                        f"نتمنى أن تكون رحلتك مع الكابتن {driver_name or 'المختص'} كانت مريحة وممتعة! 🚕\n\n"
                        f"يهمنا جداً رأيك لتحسين خدماتنا.\n"
                        f"يرجى الرد بتقييمك من 1 إلى 5 نجوم ⭐\n"
                        f"وأي ملاحظات إضافية ترغب في مشاركتها.\n\n"
                        f"شكراً لاختيارك 24Seven! ✨"
                    )

                    # ✅ إصلاح مكرر: سجّل أولاً قبل الإرسال
                    sheet.update_cell(real_idx, 26, "جاري الإرسال...")
                    time.sleep(1)
                    if send_linked_whatsapp(cust_phone, fb_msg, task_instance):
                        sheet.update_cell(real_idx, 26, "تم طلب التقييم ✅")
                        sent_cache[cache_key_feedback] = True
                        save_sent_cache(sent_cache)
                    else:
                        sheet.update_cell(real_idx, 26, "")
                    time.sleep(3)

        print("💤 انتظار 30 ثانية قبل الفحص التالي...")
        time.sleep(30)

    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "Quota exceeded" in err_msg:
            print("⏳ [حد أقتباس Google Sheets] تم الوصول للحد الأقصى لطلبات جوجل شيت (429). جاري التوقف المؤقت لمدة 45 ثانية لتصفير الحصة...")
            time.sleep(45)
        elif "SSL" in err_msg or "ConnectionPool" in err_msg or "Max retries" in err_msg or "EOF" in err_msg:
            print("⚠️ انقطاع مؤقت في الاتصال بجوجل شيت، جاري إعادة المحاولة تلقائياً خلال 10 ثوانٍ...")
            time.sleep(10)
        else:
            print(f"⚠️ خطأ في الدورة: {e}")
            traceback.print_exc()
            time.sleep(10)