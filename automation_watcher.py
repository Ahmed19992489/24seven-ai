import time
import traceback
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from datetime import datetime, timedelta
import re
import os

# =====================================================
# ⚙️ إعدادات النظام
# =====================================================
WHATSAPP_TOKEN = "EAAPDbwUyvY0BQrm6ZB9qb62LU9hI50ZC9QOfZAO3VPA7ZCSnFSRMCb2kouBRkXu4LiVmRU2ydv1vLl00kKmgTFMN5ULJOpImor7i8oITjicjIjWiOLxTL7yltYrlF0RLxcdU6UNOaIdqo4Ouv0BnQ79OK2sgSLpHY9ZCQs4iRIxcpjnoxr8EWpV4FSgGTzgZDZD"
PHONE_ID = "597129733493778"
SHEET_NAME = "امر حجز عميل"

# أسماء القوالب (Templates)
TMPL_CONFIRM_TOMORROW = "trip_confirm_request"   # تأكيد الحجز
TMPL_DRIVER_TO_CLIENT = "driver_details_assigned" # بيانات السائق للعميل
TMPL_ORDER_TO_DRIVER  = "trip_order_driver"       # أمر الشغل للسائق
TMPL_FEEDBACK         = "trip_feedback_start"     # تقييم الرحلة

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

def clean_phone(phone):
    """تجهيز الرقم ليقبل الإرسال - يدعم الأرقام المصرية والدولية"""
    if not phone: return None
    
    # تنظيف الرقم من أي مسافات أو رموز
    clean = re.sub(r'\D', '', str(phone))
    
    # إزالة الأصفار البادئة (00)
    if clean.startswith("00"):
        clean = clean[2:]
        
    # معالجة تنسيق الأرقام المصرية (01...)
    if clean.startswith("01") and len(clean) == 11:
        return "2" + clean
    if clean.startswith("1") and len(clean) == 10:
        return "20" + clean
        
    # إعادة الرقم كما هو إذا كان طوله مقبول (دولي)
    return clean if len(clean) > 9 else None

def parse_smart_date(date_str):
    if not date_str: return None
    date_str = str(date_str).strip().split(' ')[0]
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    return None

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    return client.open_by_url('https://docs.google.com/spreadsheets/d/1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4/edit').worksheet(SHEET_NAME)

def send_template(to, template_name, lang="ar", params=[]):
    if not to: return False
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    
    # تنظيف كل البارامترات قبل الإرسال
    cleaned_params = []
    for p in params:
        cleaned_params.append({"type": "text", "text": clean_param(p["text"])})

    payload = {
        "messaging_product": "whatsapp", 
        "to": "+" + to, 
        "type": "template",
        "template": {
            "name": template_name, 
            "language": {"code": lang}, 
            "components": [{"type": "body", "parameters": cleaned_params}]
        }
    }
    try:
        r = requests.post(url, json=payload, headers=headers)
        if r.status_code == 200: 
            print(f"✅ Sent {template_name} to {to}")
            return True
        print(f"❌ Error sending {template_name}: {r.text}")
        return False
    except Exception as e:
        print(f"❌ Exception: {e}")
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
        
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        today = datetime.now().date()
        
        if len(rows) > 1:
            for i, row in enumerate(rows[1:]):
                real_idx = i + 2
                while len(row) < 45: row.append("") 

                # قراءة البيانات
                raw_date = row[1]
                trip_time = row[2]
                cust_name = row[3]
                cust_phone = clean_phone(row[4])
                
                pickup = row[6]
                dropoff = row[7]
                price = row[12]
                notes = row[14]
                
                driver_name = row[21] 
                driver_phone = clean_phone(row[22]) 
                
                # قراءة الحالات (الأعمدة Y, Z, AA)
                msg_driver_status = row[24]   
                msg_feedback_status = row[25] 
                msg_confirm_status = row[26]  
                
                # قراءة اللوكيشن
                location_url = str(row[28]).strip()

                t_date = parse_smart_date(raw_date)

                # -------------------------------------------
                # 1️⃣ فحص "تأكيد الرحلة" (للرحلات الجديدة)
                # -------------------------------------------
                if (t_date == tomorrow or t_date == today) and msg_confirm_status.strip() == "" and cust_phone:
                    print(f"🔎 صف {real_idx}: رحلة جديدة ({cust_name})...")
                    print(f"📨 جاري إرسال تأكيد الحجز للرقم: +{cust_phone}...")
                    
                    # نستخدم clean_param داخل send_template تلقائياً الآن
                    p = [
                        {"text": cust_name}, 
                        {"text": str(t_date)}, 
                        {"text": str(trip_time)}
                    ]
                    
                    if send_template(cust_phone, TMPL_CONFIRM_TOMORROW, "ar_EG", p):
                        sheet.update_cell(real_idx, 27, "تم طلب التأكيد ✅")

                # -------------------------------------------
                # 2️⃣ إبلاغ السائق والعميل (عند تعيين سائق)
                # -------------------------------------------
                if driver_name.strip() != "" and msg_driver_status.strip() == "" and cust_phone:
                    # أ) للعميل
                    p_client = [
                        {"text": cust_name}, 
                        {"text": driver_name}, 
                        {"text": str(row[22])}, 
                        {"text": str(row[10])}, 
                        {"text": "24Seven"}
                    ]
                    s1 = send_template(cust_phone, TMPL_DRIVER_TO_CLIENT, "ar", p_client)

                    # ب) للسائق (رسالة التفاصيل)
                    if driver_phone:
                        notes_content = f"{notes} | ⚠️ عميل VIP"
                        if location_url and len(location_url) > 5:
                            notes_content += f" | 📍 {location_url}"
                        notes_content += " | ☎️ 01121748885"
                        
                        p_driver = [
                            {"text": driver_name}, 
                            {"text": str(raw_date)}, 
                            {"text": str(trip_time)}, 
                            {"text": cust_name}, 
                            {"text": str(row[4])}, 
                            {"text": pickup}, 
                            {"text": dropoff}, 
                            {"text": price}, 
                            {"text": notes_content}
                        ]
                        s2 = send_template(driver_phone, TMPL_ORDER_TO_DRIVER, "ar", p_driver)

                        if s2:
                            sheet.update_cell(real_idx, 25, "تم ابلاغ الطرفين")
                    
                    elif s1:
                        sheet.update_cell(real_idx, 25, "تم ابلاغ العميل فقط")

                # -------------------------------------------
                # 3️⃣ الفيدباك (بعد انتهاء الرحلة)
                # -------------------------------------------
                # فحص الحالة اليدوية (تم/إنهاء)
                is_done_manual = False
                for col_idx in range(34, 39):
                    if "تم" in str(row[col_idx]) or "انهاء" in str(row[col_idx]):
                        is_done_manual = True
                        break

                should_send_feedback = False
                if is_done_manual: should_send_feedback = True
                elif t_date and t_date < today: should_send_feedback = True

                if should_send_feedback and msg_feedback_status.strip() == "" and cust_phone:
                    p_fb = [{"text": cust_name}, {"text": driver_name if driver_name else "الكابتن"}]
                    if send_template(cust_phone, TMPL_FEEDBACK, "ar", p_fb):
                        sheet.update_cell(real_idx, 26, "تم طلب التقييم")

        print("💤 انتظار 30 ثانية قبل الفحص التالي...")
        time.sleep(30)

    except Exception as e:
        print(f"⚠️ خطأ في الدورة: {e}")
        time.sleep(30)