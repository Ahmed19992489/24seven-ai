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

SUPABASE_URL = 'https://khskudtxbypohvnreloi.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I'
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
                elif r.status_code == 402 or 'exceed_egress_quota' in r.text:
                    if i == 0:
                        print_log("⏳ [Supabase Restricted 402] السحابة محظورة بسبب الباندويث. تم توقيف المزامنة السحابية مؤقتاً والاعتماد على لجوجل شيت.")
                    errors += len(batch)
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
            r_trips = requests.get(f"{SUPABASE_URL}/rest/v1/google_reservations?select=sheet_row,modified_driver_name,modified_driver_phone,trip_status,driver_msg_status,sql_server_id", headers=SUPABASE_HEADERS, timeout=15)
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

        # فحص الحجوزات السحابية الجديدة وغير الموجودة بالشيت لدفعها فوراً
        try:
            r_missing = requests.get(f"{SUPABASE_URL}/rest/v1/google_reservations?sheet_row=is.null&order=created_at.asc&limit=15", headers=SUPABASE_HEADERS, timeout=10)
            if r_missing.status_code == 200:
                missing_res = r_missing.json()
                for m_res in missing_res:
                    res_id = m_res.get('id')
                    m_name = m_res.get('customer_name') or 'عميل'
                    m_date = (m_res.get('trip_date') or '').replace('-', '/')
                    m_time = m_res.get('trip_time') or ''
                    m_phone = str(m_res.get('customer_phone') or '')
                    m_whatsapp = str(m_res.get('whatsapp_num') or m_phone)
                    m_pickup = m_res.get('pickup_address') or ''
                    m_dropoff = m_res.get('dropoff_address') or ''
                    m_pax = str(m_res.get('passengers') or '1')
                    m_bags = str(m_res.get('bags') or '0')
                    m_car = m_res.get('car_type') or 'سيدان'
                    m_status = m_res.get('client_status') or 'عميل ويب'
                    m_cost = str(m_res.get('cost') or '0')
                    m_email = m_res.get('email') or ''
                    m_notes = m_res.get('notes') or ''
                    m_type = m_res.get('trip_type') or 'ذهاب فقط'
                    m_web_id = str(res_id)
                    m_emp = m_res.get('booking_employee') or 'موقع الويب'
                    m_ts = datetime.now().strftime('%Y/%m/%d %H:%M:%S')

                    new_row = [m_ts, m_date, m_time, m_name, m_phone, m_whatsapp, m_pickup, m_dropoff, m_pax, m_bags, m_car, m_status, m_cost, m_email, m_notes, m_type, m_web_id, m_emp]
                    worksheet.append_row(new_row, value_input_option='USER_ENTERED')
                    current_last_row = len(worksheet.get_all_values())
                    requests.patch(f"{SUPABASE_URL}/rest/v1/google_reservations?id=eq.{res_id}", headers=SUPABASE_HEADERS, json={'sheet_row': current_last_row})
                    print_log(f"📥 تم ترحيل حجز جديد من الويب ({m_name} - {m_phone}) إلى الشيت في السطر {current_last_row}")
        except Exception as e_push:
            print_log(f"⚠️ تحذير: خطأ أثناء فحص الحجوزات السحابية الجديدة: {e_push}")

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

            # [التزامن العكسي] تحديث السائق وحالة الرحلة وحالة الإبلاغ من قاعدة البيانات إلى الشيت إذا كانت فارغة في الشيت ومملوءة في قاعدة البيانات
            db_record = existing_trips_map.get(real_row_index)
            if db_record:
                db_driver = safe_str(db_record.get('modified_driver_name')).strip()
                db_driver_phone = safe_str(db_record.get('modified_driver_phone')).strip()
                db_trip_status = safe_str(db_record.get('trip_status')).strip()
                db_driver_msg_status = safe_str(db_record.get('driver_msg_status')).strip()
                db_sql_id = safe_str(db_record.get('sql_server_id')).strip()
                
                sheet_driver = safe_str(row[21]).strip()
                sheet_driver_phone = safe_str(row[22]).strip()
                sheet_trip_status = safe_str(row[34]).strip()
                sheet_driver_msg_status = safe_str(row[24]).strip()
                sheet_sql_id = safe_str(row[20]).strip()
                
                if db_driver and not sheet_driver:
                    print_log(f"📝 تحديث اسم السائق للصف {real_row_index} من قاعدة البيانات: {db_driver}")
                    worksheet.update_cell(real_row_index, 22, db_driver)
                    row[21] = db_driver
                    
                if db_driver_phone and not sheet_driver_phone:
                    worksheet.update_cell(real_row_index, 23, db_driver_phone)
                    row[22] = db_driver_phone

                if db_sql_id and not sheet_sql_id:
                    print_log(f"📝 تحديث SQL_ID للصف {real_row_index} من قاعدة البيانات: {db_sql_id}")
                    worksheet.update_cell(real_row_index, 21, db_sql_id)
                    row[20] = db_sql_id

                if db_driver_msg_status and not sheet_driver_msg_status:
                    print_log(f"📝 تحديث حالة إبلاغ السائق للصف {real_row_index} من قاعدة البيانات: {db_driver_msg_status}")
                    worksheet.update_cell(real_row_index, 25, db_driver_msg_status)
                    row[24] = db_driver_msg_status
                    
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
