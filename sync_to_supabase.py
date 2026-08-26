import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
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
SUPABASE_SERVICE_ROLE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjMxMjAyOSwiZXhwIjoyMTAxODg4MDI5fQ.uyCTVGkoeoz4xB3r2muV_fLiI62QIw-65g2nVeIb62w'
SUPABASE_HEADERS = {
    'apikey': SUPABASE_SERVICE_ROLE_KEY,
    'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates'
}

SHEET_URL = 'https://docs.google.com/spreadsheets/d/1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4/edit'
SHEET_NAME = 'امر حجز عميل'

SYNC_INTERVAL = 300  # كل 5 دقائق (تم رفعه من 2 لتقليل Bandwidth)
SUPABASE_BLOCKED_UNTIL = 0  # timestamp - يوقف المزامنة السحابية تلقائياً عند 402

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

def upsert_to_supabase(records):
    """رفع السجلات المتغيرة فقط إلى Supabase — يقلل Egress بـ 95%"""
    global SUPABASE_BLOCKED_UNTIL
    
    if not records:
        return 0, 0
    
    # تحقق من حالة الحظر (402)
    if time.time() < SUPABASE_BLOCKED_UNTIL:
        remaining = int(SUPABASE_BLOCKED_UNTIL - time.time()) // 60
        print_log(f"⛔ Supabase محظورة حتى انتهاء الحصة — {remaining} دقيقة متبقية. (جاري الاعتماد على Google Sheet فقط)")
        return 0, len(records)
    
    records_with_id = [r for r in records if "id" in r]
    unique_by_id = {}
    for r in records_with_id:
        unique_by_id[r["id"]] = r
    records_with_id = list(unique_by_id.values())
    records_without_id = [r for r in records if "id" not in r]
    
    success = 0
    errors = 0
    batch_size = 100

    def _is_blocked(resp):
        """True اذا كان الرد 402 من Supabase"""
        return resp.status_code == 402 or (
            resp.status_code >= 400 and 
            ('exceed_egress_quota' in resp.text or 'exceed_realtime' in resp.text or 'restricted' in resp.text.lower())
        )
    
    # 1. رفع السجلات التي تحتوي على id (on_conflict=id)
    if records_with_id:
        print_log(f"🔄 رفع {len(records_with_id)} سجل متغير بواسطة ID...")
        url_id = f"{SUPABASE_URL}/rest/v1/google_reservations?on_conflict=id"
        for i in range(0, len(records_with_id), batch_size):
            batch = records_with_id[i:i+batch_size]
            try:
                r = requests.post(url_id, headers=SUPABASE_HEADERS, json=batch, timeout=15)
                if r.status_code in [200, 201]:
                    success += len(batch)
                elif _is_blocked(r):
                    print_log(f"⛔ [402] Supabase حظرت المشروع. توقيف المزامنة لمدة 30 دقيقة تلقائياً...")
                    SUPABASE_BLOCKED_UNTIL = time.time() + 1800  # 30 دقيقة
                    errors += len(records)  # احسب كل السجلات كأخطاء
                    return success, errors
                else:
                    print_log(f"   ⚠️ خطأ في الدفعة (ID) {i//batch_size + 1}: {r.status_code} - {r.text[:150]}")
                    errors += len(batch)
            except Exception as e_post:
                print_log(f"   ⚠️ خطأ استدعاء (ID) {i//batch_size + 1}: {e_post}")
                errors += len(batch)
                
def upsert_to_neon(records):
    """رفع السجلات مباشرة إلى قاعدة بيانات Neon Postgres (Vercel) بدون أي قيود أو حظر"""
    if not records:
        return 0, 0
    try:
        import pg8000.native
        import ssl
        
        NEON_USER = "neondb_owner"
        NEON_PASSWORD = "npg_VM4tSBwN5PGd"
        NEON_HOST = "ep-plain-rice-auzortld-pooler.c-10.us-east-1.aws.neon.tech"
        NEON_DB = "neondb"
        
        con = pg8000.native.Connection(
            user=NEON_USER,
            password=NEON_PASSWORD,
            host=NEON_HOST,
            port=5432,
            database=NEON_DB,
            ssl_context=ssl.create_default_context()
        )
        
        BATCH_SIZE = 100
        success = 0
        
        for b_start in range(0, len(records), BATCH_SIZE):
            batch = records[b_start:b_start+BATCH_SIZE]
            placeholders = []
            kwargs = {}
            
            for idx, r in enumerate(batch):
                row_fields = []
                keys = [
                    "sheet_row", "sheet_timestamp", "trip_date", "trip_time", "customer_name", "customer_phone",
                    "whatsapp_num", "pickup_address", "dropoff_address", "passengers", "bags", "car_type",
                    "client_status", "cost", "email", "notes", "trip_type", "booking_employee",
                    "status", "sql_server_id", "modified_driver_name", "modified_driver_phone",
                    "driver_msg_status", "review_msg_status", "confirm_msg_status", "client_decision",
                    "location_link", "rating_stars", "car_cleanliness", "driver_behavior",
                    "recommend_us", "suggestions", "trip_status"
                ]
                for k in keys:
                    param_k = f"{k}_{idx}"
                    row_fields.append(f":{param_k}")
                    kwargs[param_k] = r.get(k, "")
                placeholders.append(f"({', '.join(row_fields)}, NOW())")
                
            sql = f"""
            INSERT INTO google_reservations (
                sheet_row, sheet_timestamp, trip_date, trip_time, customer_name, customer_phone,
                whatsapp_num, pickup_address, dropoff_address, passengers, bags, car_type,
                client_status, cost, email, notes, trip_type, booking_employee,
                status, sql_server_id, modified_driver_name, modified_driver_phone,
                driver_msg_status, review_msg_status, confirm_msg_status, client_decision,
                location_link, rating_stars, car_cleanliness, driver_behavior,
                recommend_us, suggestions, trip_status, updated_at
            ) VALUES {', '.join(placeholders)}
            ON CONFLICT (sheet_row) DO UPDATE SET
                sheet_timestamp = EXCLUDED.sheet_timestamp,
                trip_date = EXCLUDED.trip_date,
                trip_time = EXCLUDED.trip_time,
                customer_name = EXCLUDED.customer_name,
                customer_phone = EXCLUDED.customer_phone,
                whatsapp_num = EXCLUDED.whatsapp_num,
                pickup_address = EXCLUDED.pickup_address,
                dropoff_address = EXCLUDED.dropoff_address,
                passengers = EXCLUDED.passengers,
                bags = EXCLUDED.bags,
                car_type = EXCLUDED.car_type,
                client_status = EXCLUDED.client_status,
                cost = EXCLUDED.cost,
                email = EXCLUDED.email,
                notes = EXCLUDED.notes,
                trip_type = EXCLUDED.trip_type,
                booking_employee = EXCLUDED.booking_employee,
                status = EXCLUDED.status,
                sql_server_id = EXCLUDED.sql_server_id,
                modified_driver_name = EXCLUDED.modified_driver_name,
                modified_driver_phone = EXCLUDED.modified_driver_phone,
                driver_msg_status = EXCLUDED.driver_msg_status,
                review_msg_status = EXCLUDED.review_msg_status,
                confirm_msg_status = EXCLUDED.confirm_msg_status,
                client_decision = EXCLUDED.client_decision,
                location_link = EXCLUDED.location_link,
                rating_stars = EXCLUDED.rating_stars,
                car_cleanliness = EXCLUDED.car_cleanliness,
                driver_behavior = EXCLUDED.driver_behavior,
                recommend_us = EXCLUDED.recommend_us,
                suggestions = EXCLUDED.suggestions,
                trip_status = EXCLUDED.trip_status,
                updated_at = NOW();
            """
            con.run(sql, **kwargs)
            success += len(batch)
            
        con.close()
        return success, 0
    except Exception as e_neon:
        print_log(f"⚠️ خطأ في مزامنة Neon Postgres: {e_neon}")
        return 0, len(records)



# =======================================================
# البرنامج الرئيسي
# =======================================================
print("\n" + "="*60)
print("   مزامنة Google Sheet → Supabase (أوامر الحجز)   ")
print("   يعمل كل دقيقتين تلقائياً   ")
print("="*60 + "\n")

# ذاكرة تخزين مؤقت للمزامنة الذكية (لتتبع ما تغير فعلاً)
_last_sync_fingerprints = {}  # sheet_row -> fingerprint
_FULL_SYNC_EVERY = 6  # كل 6 دورات (30 دقيقة) نعمل مزامنة كاملة مرة
_sync_cycle_count = 0

while True:
    try:
        _sync_cycle_count += 1
        is_full_sync = (_sync_cycle_count % _FULL_SYNC_EVERY == 1)  # دورة كاملة كل 30 دقيقة
        print_log(f"🚀 بدء دورة مزامنة {'كاملة' if is_full_sync else 'تدريجية'} (#{_sync_cycle_count})...")

        # جلب تفاصيل الرحلات الموجودة — لكن فقط الحقول الضرورية لتقليل Egress
        existing_trips_map = {}
        if time.time() >= SUPABASE_BLOCKED_UNTIL:  # لا نحاول لو محظور
            try:
                # ✂️ نجيب فقط الحقول اللي بنحتاجها فعلاً لمقارنة التغييرات
                r_trips = requests.get(
                    f"{SUPABASE_URL}/rest/v1/google_reservations"
                    f"?select=sheet_row,modified_driver_name,modified_driver_phone,trip_status,driver_msg_status,sql_server_id,client_decision,confirm_msg_status,status"
                    f"&sheet_row=not.is.null",
                    headers=SUPABASE_HEADERS, timeout=15
                )
                if r_trips.status_code == 200:
                    for t in r_trips.json():
                        s_row = t.get('sheet_row')
                        if s_row is not None:
                            existing_trips_map[int(s_row)] = t
                elif r_trips.status_code == 402:
                    print_log(f"⛔ [402] Supabase محظورة عند جلب البيانات. توقيف 30 دقيقة...")
                    SUPABASE_BLOCKED_UNTIL = time.time() + 1800
            except Exception as e_trips:
                print_log(f"⚠️ تحذير: فشل جلب معرفات الرحلات: {e_trips}")

        # الاتصال بـ Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL)
        worksheet = sheet.worksheet(SHEET_NAME)

        # فحص الحجوزات السحابية الجديدة وغير الموجودة بالشيت لدفعها فوراً
        try:
            if time.time() >= SUPABASE_BLOCKED_UNTIL:  # لا نحاول لو محظور
                r_missing = requests.get(
                    f"{SUPABASE_URL}/rest/v1/google_reservations?sheet_row=is.null&order=created_at.asc&limit=15",
                    headers=SUPABASE_HEADERS, timeout=10
                )
                if r_missing.status_code == 200:
                    missing_res = r_missing.json()
                    
                    # نجلب بيانات الشيت الحالية للتحقق من التكرار مسبقاً
                    all_sheet_vals = worksheet.get_all_values()
                    
                    for m_res in missing_res:
                        res_id = m_res.get('id')
                        m_name = (m_res.get('customer_name') or '').strip()
                        m_phone = str(m_res.get('customer_phone') or '').strip()
                        if not m_name or m_name == 'عميل' or not m_phone or len(clean_phone(m_phone)) < 8:
                            continue
                        m_date = (m_res.get('trip_date') or '').replace('-', '/')
                        m_time = m_res.get('trip_time') or ''
                        
                        # ✅ فحص 1: هل يوجد نفس الحجز بالفعل في الشيت (نفس الهاتف + التاريخ + الوقت)؟
                        clean_m_phone = clean_phone(m_phone)
                        duplicate_in_sheet = False
                        duplicate_row_num = -1
                        for si, srow in enumerate(all_sheet_vals[1:], start=2):
                            while len(srow) < 17: srow.append('')
                            sheet_phone = clean_phone(str(srow[4]))  # عمود E
                            sheet_date = str(srow[1]).strip()        # عمود B
                            sheet_time = str(srow[2]).strip()        # عمود C
                            sheet_web_id = str(srow[16]).strip()     # عمود Q (web_id)
                            
                            # تطابق بـ web_id (الأدق)
                            if sheet_web_id == str(res_id):
                                duplicate_in_sheet = True
                                duplicate_row_num = si
                                break
                            # أو تطابق بهاتف + تاريخ + وقت
                            if (len(clean_m_phone) >= 8 and clean_m_phone[-8:] == sheet_phone[-8:] and
                                m_date and sheet_date and m_date.replace('/', '-').split('T')[0] == sheet_date.replace('/', '-').split('T')[0] and
                                m_time.strip()[:5] == sheet_time.strip()[:5]):
                                duplicate_in_sheet = True
                                duplicate_row_num = si
                                break
                        
                        if duplicate_in_sheet:
                            # الصف موجود في الشيت لكن sheet_row غير محدث في Supabase — نصلحه فقط
                            if duplicate_row_num > 0:
                                patch_r = requests.patch(
                                    f"{SUPABASE_URL}/rest/v1/google_reservations?id=eq.{res_id}",
                                    headers=SUPABASE_HEADERS, json={'sheet_row': duplicate_row_num}, timeout=5
                                )
                                if patch_r.status_code in [200, 204]:
                                    print_log(f"🔗 ربط حجز موجود ({m_name} - {m_phone}) بسطر الشيت {duplicate_row_num} (لم يكن مرتبطاً)")
                                else:
                                    print_log(f"⚠️ فشل ربط الحجز الموجود ({m_name}): {patch_r.status_code}")
                            continue  # ⛔ لا تضيف مجدداً
                        
                        # ✅ الحجز جديد فعلاً — أضفه للشيت
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

                        # 🔒 تنظيف أرقام الهاتف: إزالة + والمسافات لمنع #ERROR! في Google Sheets
                        # Google Sheets يفسر +20... كـ formula فيعطي #ERROR!
                        def safe_phone(p):
                            p = str(p).strip()
                            # إزالة + من البداية فقط
                            p = re.sub(r'^\+', '', p)
                            # إزالة المسافات
                            p = p.replace(' ', '')
                            return p
                        
                        m_phone_safe = safe_phone(m_phone)
                        m_whatsapp_safe = safe_phone(m_whatsapp)

                        new_row = [m_ts, m_date, m_time, m_name, m_phone_safe, m_whatsapp_safe, m_pickup, m_dropoff, m_pax, m_bags, m_car, m_status, m_cost, m_email, m_notes, m_type, m_web_id, m_emp]
                        worksheet.append_row(new_row, value_input_option='USER_ENTERED')
                        current_last_row = len(worksheet.get_all_values())
                        
                        # محاولة PATCH بإعادة المحاولة 3 مرات لضمان تحديث sheet_row
                        patch_success = False
                        for attempt in range(3):
                            try:
                                patch_r = requests.patch(
                                    f"{SUPABASE_URL}/rest/v1/google_reservations?id=eq.{res_id}",
                                    headers=SUPABASE_HEADERS, json={'sheet_row': current_last_row}, timeout=8
                                )
                                if patch_r.status_code in [200, 204]:
                                    patch_success = True
                                    break
                                elif patch_r.status_code == 402:
                                    SUPABASE_BLOCKED_UNTIL = time.time() + 1800
                                    break
                                time.sleep(1)
                            except Exception:
                                time.sleep(2)
                        
                        if patch_success:
                            print_log(f"📥 تم ترحيل حجز جديد ({m_name} - {m_phone}) إلى الشيت سطر {current_last_row}")
                        else:
                            print_log(f"⚠️ تم إضافة الحجز ({m_name}) للشيت سطر {current_last_row} لكن فشل تحديث sheet_row في Supabase")
                elif r_missing.status_code == 402:
                    SUPABASE_BLOCKED_UNTIL = time.time() + 1800
                    print_log("⛔ [402] Supabase محظورة عند فحص الحجوزات الجديدة. توقيف 30 دقيقة...")
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

            # [التزامن الثنائي] تحديث بيانات الشيت من قاعدة البيانات
            db_record = existing_trips_map.get(real_row_index)
            if db_record:
                db_driver = safe_str(db_record.get('modified_driver_name')).strip()
                db_driver_phone = safe_str(db_record.get('modified_driver_phone')).strip()
                db_trip_status = safe_str(db_record.get('trip_status')).strip()
                db_driver_msg_status = safe_str(db_record.get('driver_msg_status')).strip()
                db_sql_id = safe_str(db_record.get('sql_server_id')).strip()
                db_decision = safe_str(db_record.get('client_decision')).strip()
                db_confirm = safe_str(db_record.get('confirm_msg_status')).strip()
                
                sheet_driver = safe_str(row[21]).strip()
                sheet_driver_phone = safe_str(row[22]).strip()
                sheet_trip_status = safe_str(row[34]).strip()
                sheet_driver_msg_status = safe_str(row[24]).strip()
                sheet_sql_id = safe_str(row[20]).strip()
                sheet_confirm = safe_str(row[26]).strip()
                sheet_decision = safe_str(row[27]).strip()
                
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
                    
                if db_decision and db_decision != sheet_decision:
                    print_log(f"📝 تحديث قرار العميل للصف {real_row_index} من قاعدة البيانات: {db_decision}")
                    worksheet.update_cell(real_row_index, 28, db_decision)
                    row[27] = db_decision

                if db_confirm and db_confirm != sheet_confirm:
                    print_log(f"📝 تحديث تأكيد الحجز للصف {real_row_index} من قاعدة البيانات: {db_confirm}")
                    worksheet.update_cell(real_row_index, 27, db_confirm)
                    row[26] = db_confirm

                if db_trip_status and db_trip_status != sheet_trip_status:
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
            if safe_str(row[16]).isdigit():
                record["id"] = int(row[16])
            records.append(record)

        print_log(f"📊 إجمالي الصفوف المعالجة: {len(records)}")

        # ✂️ فلترة ذكية: رفع السجلات التي تغيرت فعلاً فقط (تقليل Egress بـ 95%)
        if not is_full_sync:
            changed_records = []
            for rec in records:
                key = rec.get('sheet_row')
                # نحسب بصمة سريعة للسجل (الحقول الأساسية)
                fp = f"{rec.get('trip_status')}|{rec.get('modified_driver_name')}|{rec.get('client_decision')}|{rec.get('cost')}|{rec.get('confirm_msg_status')}"
                if key not in _last_sync_fingerprints or _last_sync_fingerprints[key] != fp:
                    changed_records.append(rec)
                    _last_sync_fingerprints[key] = fp
            
            if not changed_records:
                print_log(f"✅ لا توجد تغييرات — تخطي الرفع لـ Supabase (توفير Bandwidth)")
            else:
                print_log(f"📤 {len(changed_records)} سجل تغير من أصل {len(records)} — رفع المتغير فقط...")
                # 1. رفع لـ Neon Postgres (Vercel)
                neon_s, neon_e = upsert_to_neon(changed_records)
                if neon_s > 0:
                    print_log(f"✅ تم تحديث {neon_s} سجل في Neon Postgres (Vercel)")
                # 2. رفع لـ Supabase
                success, errors = upsert_to_supabase(changed_records)
                if errors == 0:
                    print_log(f"✅ تمت المزامنة التدريجية بنجاح ({success} سجل)")
                else:
                    print_log(f"⚠️ تمت المزامنة مع {errors} خطأ ({success} نجح)")
        else:
            # مزامنة كاملة كل 30 دقيقة
            # تحديث البصمات بالكامل
            for rec in records:
                key = rec.get('sheet_row')
                fp = f"{rec.get('trip_status')}|{rec.get('modified_driver_name')}|{rec.get('client_decision')}|{rec.get('cost')}|{rec.get('confirm_msg_status')}"
                _last_sync_fingerprints[key] = fp
            # 1. رفع لـ Neon Postgres (Vercel)
            neon_s, neon_e = upsert_to_neon(records)
            if neon_s > 0:
                print_log(f"✅ تمت المزامنة الكاملة لـ Neon Postgres بنجاح ({neon_s} سجل)")
            # 2. رفع لـ Supabase
            success, errors = upsert_to_supabase(records)
            if errors == 0:
                print_log(f"✅ تمت المزامنة الكاملة بنجاح ({success} سجل)")
            else:
                print_log(f"⚠️ تمت المزامنة الكاملة مع {errors} خطأ ({success} نجح)")


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
