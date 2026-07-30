import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import os
import requests
import json

# =======================================================
# إعدادات
# =======================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
creds_path = os.path.join(current_dir, 'credentials.json')

SUPABASE_URL = 'https://wtjwzqvmwnbvjxnmweqq.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NjU0MDMsImV4cCI6MjA4NzA0MTQwM30.kTFK22b18cc1BmvMyLTt-7V113jyf_YrodSB7Km00tY'
SUPABASE_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates'
}

SHEET_URL = 'https://docs.google.com/spreadsheets/d/1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4/edit'
SHEET_NAME = 'امر حجز عميل'

SYNC_INTERVAL = 120  # كل دقيقتين

# =======================================================
# دوال مساعدة
# =======================================================
def print_log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}")

def safe_str(val):
    return str(val).strip() if val is not None else ""

def safe_num(val):
    try:
        return float(str(val).replace(',', '').strip()) if val else 0
    except:
        return 0

def clean_phone(phone_str):
    import re
    return re.sub(r'\D', '', str(phone_str)) if phone_str else ""

def clean_date(val):
    if not val: return None
    try:
        val = str(val).strip()
        # يدعم صيغ التواريخ المختلفة
        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%m-%d-%Y']:
            try:
                return datetime.strptime(val.split(' ')[0], fmt).strftime('%Y-%m-%d')
            except:
                pass
    except:
        pass
    return None
    return None

def upsert_to_supabase(records):
    """رفع السجلات إلى Supabase بـ upsert حسب المعرف أو sheet_row"""
    if not records:
        return 0, 0
    
    records_with_id = [r for r in records if "id" in r]
    # Filter to ensure unique IDs in batch
    unique_by_id = {}
    for r in records_with_id:
        unique_by_id[r["id"]] = r
    records_with_id = list(unique_by_id.values())
    
    records_without_id = [r for r in records if "id" not in r]
    
    success = 0
    errors = 0
    batch_size = 100
    
    # 0. تنظيف الصفوف المتعارضة لمنع خطأ constraint unique_sheet_row
    if records_with_id:
        print_log(f"🧹 تنظيف التعارضات المحتملة لـ {len(records_with_id)} سجل...")
        sheet_rows = [r['sheet_row'] for r in records_with_id if r.get('sheet_row')]
        # نقسم الصفوف لمجموعات لتفادي تجاوز طول الرابط
        chunk_size = 100
        for idx in range(0, len(sheet_rows), chunk_size):
            chunk = sheet_rows[idx:idx+chunk_size]
            chunk_str = ",".join(map(str, chunk))
            try:
                # نجلب السجلات التي تملك نفس الصفوف في الشيت
                check_url = f"{SUPABASE_URL}/rest/v1/google_reservations?sheet_row=in.({chunk_str})&select=id,sheet_row"
                resp = requests.get(check_url, headers=SUPABASE_HEADERS, timeout=15)
                if resp.status_code == 200:
                    existing_db_records = resp.json()
                    # خريطة لمعرفات الصفوف التي ننوي رفعها
                    planned_ids = {r['sheet_row']: r['id'] for r in records_with_id if r.get('sheet_row')}
                    
                    for db_rec in existing_db_records:
                        db_row = db_rec.get('sheet_row')
                        db_id = db_rec.get('id')
                        # إذا كان المعرف في قاعدة البيانات مختلفاً عن المعرف المخطط له لنفس الصف، نقوم بمسح القديم لمنع التعارض
                        if db_row in planned_ids and db_id != planned_ids[db_row]:
                            print_log(f"   🧹 حذف التعارض للصف {db_row}: معرف قاعدة البيانات {db_id} لا يطابق المعرف المخطط {planned_ids[db_row]}")
                            del_url = f"{SUPABASE_URL}/rest/v1/google_reservations?id=eq.{db_id}"
                            requests.delete(del_url, headers=SUPABASE_HEADERS, timeout=15)
            except Exception as e_check:
                print_log(f"   ⚠️ خطأ أثناء التحقق من التعارضات: {e_check}")

    # 1. رفع السجلات التي تحتوي على id (on_conflict=id)
    if records_with_id:
        print_log(f"🔄 رفع {len(records_with_id)} سجل بواسطة ID (on_conflict=id)...")
        url_id = f"{SUPABASE_URL}/rest/v1/google_reservations?on_conflict=id"
        for i in range(0, len(records_with_id), batch_size):
            batch = records_with_id[i:i+batch_size]
            try:
                r = requests.post(url_id, headers=SUPABASE_HEADERS, json=batch, timeout=15)
                if r.status_code in [200, 201]:
                    success += len(batch)
                else:
                    print_log(f"   ⚠️ خطأ في الدفعة (ID) {i//batch_size + 1}: {r.status_code} - {r.text[:200]}")
                    errors += len(batch)
            except Exception as e_post:
                print_log(f"   ⚠️ خطأ استدعاء (ID) {i//batch_size + 1}: {e_post}")
                errors += len(batch)
                
    # 2. رفع السجلات التي لا تحتوي على id (on_conflict=sheet_row)
    if records_without_id:
        print_log(f"🔄 رفع {len(records_without_id)} سجل بواسطة sheet_row (on_conflict=sheet_row)...")
        url_row = f"{SUPABASE_URL}/rest/v1/google_reservations?on_conflict=sheet_row"
        for i in range(0, len(records_without_id), batch_size):
            batch = records_without_id[i:i+batch_size]
            try:
                r = requests.post(url_row, headers=SUPABASE_HEADERS, json=batch, timeout=15)
                if r.status_code in [200, 201]:
                    success += len(batch)
                else:
                    print_log(f"   ⚠️ خطأ في الدفعة (sheet_row) {i//batch_size + 1}: {r.status_code} - {r.text[:200]}")
                    errors += len(batch)
            except Exception as e_post:
                print_log(f"   ⚠️ خطأ استدعاء (sheet_row) {i//batch_size + 1}: {e_post}")
                errors += len(batch)
                
    return success, errors



# =======================================================
# البرنامج الرئيسي
# =======================================================
print("\n" + "="*60)
print("   مزامنة Google Sheet → Supabase (أوامر الحجز)   ")
print("   يعمل كل دقيقتين تلقائياً   ")
print("="*60 + "\n")

while True:
    try:
        print_log("🚀 بدء دورة مزامنة...")

        # جلب تفاصيل الرحلات الموجودة في قاعدة البيانات للمطابقة العكسية والتزامن الثنائي
        existing_trips_map = {}
        try:
            r_trips = requests.get(f"{SUPABASE_URL}/rest/v1/google_reservations?select=sheet_row,modified_driver_name,modified_driver_phone,trip_status", headers=SUPABASE_HEADERS, timeout=15)
            if r_trips.status_code == 200:
                for t in r_trips.json():
                    s_row = t.get('sheet_row')
                    if s_row is not None:
                        existing_trips_map[int(s_row)] = t
        except Exception as e_trips:
            print_log(f"⚠️ تحذير: فشل جلب معرفات الرحلات من قاعدة البيانات: {e_trips}")

        # الاتصال بـ Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL)
        worksheet = sheet.worksheet(SHEET_NAME)

        all_values = worksheet.get_all_values()
        if len(all_values) < 2:
            print_log("⚠️ الشيت فارغ أو يحتوي على عناوين فقط.")
            time.sleep(SYNC_INTERVAL)
            continue

        data_rows = all_values[1:]  # تخطي صف العناوين
        records = []

        for i, row in enumerate(data_rows):
            real_row_index = i + 2
            if not row or not any(row):
                continue
            # تأكد أن الصف فيه بيانات كافية
            while len(row) < 35:
                row.append("")

            # [التزامن العكسي] تحديث السائق وحالة الرحلة من قاعدة البيانات إلى الشيت إذا كانت فارغة في الشيت ومملوءة في قاعدة البيانات
            db_record = existing_trips_map.get(real_row_index)
            if db_record:
                db_driver = safe_str(db_record.get('modified_driver_name')).strip()
                db_driver_phone = safe_str(db_record.get('modified_driver_phone')).strip()
                db_trip_status = safe_str(db_record.get('trip_status')).strip()
                
                sheet_driver = safe_str(row[21]).strip()
                sheet_driver_phone = safe_str(row[22]).strip()
                sheet_trip_status = safe_str(row[34]).strip()
                
                if db_driver and not sheet_driver:
                    print_log(f"📝 تحديث اسم السائق للصف {real_row_index} من قاعدة البيانات: {db_driver}")
                    worksheet.update_cell(real_row_index, 22, db_driver)
                    row[21] = db_driver
                    
                if db_driver_phone and not sheet_driver_phone:
                    worksheet.update_cell(real_row_index, 23, db_driver_phone)
                    row[22] = db_driver_phone
                    
                if db_trip_status and not sheet_trip_status:
                    print_log(f"📝 تحديث حالة الرحلة للصف {real_row_index} من قاعدة البيانات: {db_trip_status}")
                    worksheet.update_cell(real_row_index, 35, db_trip_status)
                    row[34] = db_trip_status

            # تجاهل الصفوف التي ليس فيها اسم أو تاريخ
            customer_name = safe_str(row[3])
            trip_date = clean_date(row[1])
            if not customer_name and not trip_date:
                continue

            status_raw = safe_str(row[19])
            record = {
                "sheet_row":              real_row_index,
                "sheet_timestamp":        safe_str(row[0])[:255],
                "trip_date":              trip_date,
                "trip_time":              safe_str(row[2])[:20],
                "customer_name":          customer_name[:100],
                "customer_phone":         clean_phone(row[4])[:30],
                "whatsapp_num":           clean_phone(row[5])[:50],
                "pickup_address":         safe_str(row[6])[:500],
                "dropoff_address":        safe_str(row[7])[:500],
                "passengers":             int(safe_num(row[8])),
                "bags":                   int(safe_num(row[9])),
                "car_type":               safe_str(row[10])[:50],
                "client_status":          safe_str(row[11])[:100],
                "cost":                   safe_num(row[12]),
                "email":                  safe_str(row[13])[:255],
                "notes":                  safe_str(row[14])[:500],
                "trip_type":              safe_str(row[15])[:50],
                "commission":             "",
                "booking_employee":       safe_str(row[17])[:50],
                "ticket_image":           safe_str(row[18]),
                "status":                 status_raw[:30] if status_raw else "pending",
                "sql_server_id":          safe_str(row[20])[:20],
                "modified_driver_name":   safe_str(row[21])[:255],
                "modified_driver_phone":  safe_str(row[22])[:50],
                "column_24":              safe_str(row[23])[:255],
                "driver_msg_status":      safe_str(row[24])[:100],
                "review_msg_status":      safe_str(row[25])[:100],
                "confirm_msg_status":     safe_str(row[26])[:100],
                "client_decision":        safe_str(row[27])[:100],
                "location_link":          safe_str(row[28]),
                "rating_stars":           safe_str(row[29])[:50],
                "car_cleanliness":        safe_str(row[30])[:50],
                "driver_behavior":        safe_str(row[31])[:50],
                "recommend_us":           safe_str(row[32])[:50],
                "suggestions":            safe_str(row[33]),
                "trip_status":            safe_str(row[34])[:100],
                "updated_at":             datetime.now().isoformat()
            }
            records.append(record)

        print_log(f"📊 إجمالي الصفوف المعالجة: {len(records)}")

        success, errors = upsert_to_supabase(records)
        if errors == 0:
            print_log(f"✅ تمت المزامنة بنجاح ({success} سجل)")
        else:
            print_log(f"⚠️ تمت المزامنة مع {errors} خطأ ({success} نجح)")


    except Exception as e:
        err_str = str(e)
        if '429' in err_str or 'Quota exceeded' in err_str:
            print_log("⏳ [حد أقتباس Google Sheets] تم الوصول للحد الأقصى لطلبات جوجل شيت (429). جاري التوقف المؤقت لمدة 45 ثانية لتصفير الحصة...")
            time.sleep(45)
        else:
            print(f"\n❌ خطأ: {e}")
            print("⏳ إعادة المحاولة في الدورة القادمة...")

    print("-" * 40)
    print(f"⏳ انتظار {SYNC_INTERVAL} ثانية...")
    time.sleep(SYNC_INTERVAL)
