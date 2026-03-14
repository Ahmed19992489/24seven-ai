import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import time
import os
import re
from datetime import datetime

# =======================================================
# ⚙️ إعدادات الواتساب
# =======================================================

WHATSAPP_TOKEN = "EAAPDbwUyvY0BQrm6ZB9qb62LU9hI50ZC9QOfZAO3VPA7ZCSnFSRMCb2kouBRkXu4LiVmRU2ydv1vLl00kKmgTFMN5ULJOpImor7i8oITjicjIjWiOLxTL7yltYrlF0RLxcdU6UNOaIdqo4Ouv0BnQ79OK2sgSLpHY9ZCQs4iRIxcpjnoxr8EWpV4FSgGTzgZDZD"
PHONE_ID = "597129733493778"
TEMPLATE_NAME = "trip_confirmation"

# =======================================================
# 📂 إعدادات جوجل شيت
# =======================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
creds_path = os.path.join(current_dir, 'credentials.json')
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# =======================================================
# 🛠️ دوال مساعدة
# =======================================================
def print_log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}")

# ✅ دالة تنظيف النصوص (حماية من خطأ Meta #132018)
def clean_param(text):
    if not text: return " "
    text = str(text)
    # إزالة الأسطر الجديدة والمسافات الزائدة
    text = text.replace('\n', ' - ').replace('\r', ' ').replace('\t', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def clean_phone_for_whatsapp(phone_str):
    """تجهيز الرقم ليقبل الإرسال - يدعم الأرقام المصرية والدولية"""
    if not phone_str: return None
    
    # تحويل لنص وإزالة أي شيء غير الأرقام
    clean = re.sub(r'\D', '', str(phone_str)) 
    
    # إزالة الأصفار البادئة (00) إذا وجدت
    if clean.startswith("00"):
        clean = clean[2:]
    
    # معالجة تنسيق الأرقام المصرية
    if clean.startswith("01") and len(clean) == 11:
        return "2" + clean
    elif clean.startswith("1") and len(clean) == 10:
        return "20" + clean
    
    # إذا كان الرقم يبدأ بـ 201 فهو غالباً مصري صحيح
    # إذا كان يبدأ بـ 966 فهو سعودي
    # سنعيد الرقم كما هو إذا كان طوله منطقي (أكبر من 9)
    return clean if len(clean) > 9 else None

def send_whatsapp_template(to_mobile, cust_name, pickup, dropoff, trip_date, trip_time, cost):
    """إرسال التمبلت"""
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    # تنظيف البيانات قبل الإرسال
    name_clean = clean_param(cust_name)[:50]
    pickup_clean = clean_param(pickup)[:100]
    dropoff_clean = clean_param(dropoff)[:100]
    date_time_clean = clean_param(f"{trip_date} - {trip_time}")
    cost_clean = clean_param(str(cost))

    payload = {
        "messaging_product": "whatsapp",
        "to": "+" + to_mobile,  # إضافة علامة الزائد لضمان قبول الرقم من Meta
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {"code": "ar"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": name_clean},        # {{1}}
                        {"type": "text", "text": pickup_clean},      # {{2}}
                        {"type": "text", "text": dropoff_clean},     # {{3}}
                        {"type": "text", "text": date_time_clean},   # {{4}}
                        {"type": "text", "text": cost_clean}         # {{5}}
                    ]
                }
            ]
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            return True, "Success"
        else:
            return False, response.text
    except Exception as e:
        return False, str(e)

# =======================================================
# 🚀 المحرك الرئيسي (Main Loop)
# =======================================================
print("\n" + "="*50)
print("   🚀 مرسل تفاصيل الحجز (Whatsapp Sender V2)   ")
print("   ✅ يدعم تنظيف البيانات + التحقق من الخانات   ")
print("="*50 + "\n")

while True:
    try:
        # 1. الاتصال بجوجل شيت
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4/edit')
        worksheet = sheet.worksheet("امر حجز عميل")

        # 2. جلب البيانات
        all_rows = worksheet.get_all_values()
        
        if len(all_rows) > 1:
            data_rows = all_rows[1:]
            
            for i, row in enumerate(data_rows):
                real_row_index = i + 2 
                
                # إكمال الصفوف الناقصة
                while len(row) < 24: row.append("")

                # قراءة البيانات
                cust_name = row[3]
                phone_raw = row[4]
                # تنظيف الحالة لإزالة المسافات المخفية
                whatsapp_status = str(row[23]).strip() 

                # التحقق من الشروط: اسم موجود + هاتف موجود + حالة الواتساب فارغة تماماً
                if cust_name and phone_raw and whatsapp_status == "":
                    
                    trip_date = row[1]
                    trip_time = row[2]
                    pickup = row[6]
                    dropoff = row[7]
                    cost = row[12]
                    
                    print_log(f"🔎 صف {real_row_index}: رحلة جديدة ({cust_name})...")
                    clean_phone = clean_phone_for_whatsapp(phone_raw)
                    
                    if clean_phone:
                        print_log(f"📨 جاري إرسال رحلة ({cust_name}) للرقم: +{clean_phone}...")
                        success, error_msg = send_whatsapp_template(clean_phone, cust_name, pickup, dropoff, trip_date, trip_time, cost)
                        
                        if success:
                            worksheet.update_cell(real_row_index, 24, "تم الارسال")
                            print_log(f"✅ تم الإرسال بنجاح!")
                            time.sleep(2) 
                        else:
                            print_log(f"❌ فشل الإرسال: {error_msg}")
                            # لن نكتب "فشل" في الشيت حتى يعيد المحاولة لاحقاً، أو يمكنك تفعيل السطر التالي:
                            # worksheet.update_cell(real_row_index, 24, "فشل الارسال")
                            time.sleep(1)
                    else:
                        print_log(f"⚠️ رقم غير صالح.")
                        worksheet.update_cell(real_row_index, 24, "رقم خطأ")
                        time.sleep(2)

        print_log("⏳ انتظار 30 ثانية قبل الفحص التالي...")
        time.sleep(30)

    except Exception as e:
        error_str = str(e)
        if "Quota exceeded" in error_str or "429" in error_str:
            print_log(f"⛔ ضغط عالي (429). تفعيل وضع التبريد 60 ثانية...")
            time.sleep(60)
        else:
            print_log(f"⚠️ خطأ عام: {e}")
            time.sleep(15)