import pandas as pd
import pyodbc
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import time
import sys
import os
import re

# =======================================================
# إعدادات الاتصال والمسارات
# =======================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
creds_path = os.path.join(current_dir, 'credentials.json')

# إعدادات التوقيت
last_full_sync_time = 0
FULL_SYNC_INTERVAL = 300  # كل 5 دقائق تحديث شامل

# =======================================================
# دوال مساعدة
# =======================================================
def print_log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}")

def safe_update_cell(worksheet, row, col, value, retries=5):
    """يكتب في الشيت مع retry تلقائي عند 429"""
    for attempt in range(retries):
        try:
            worksheet.update_cell(row, col, value)
            time.sleep(1.2)  # تأخير بين كل كتابة
            return True
        except Exception as e:
            if '429' in str(e):
                wait = (attempt + 1) * 15
                print_log(f"⏳ Rate limit - انتظار {wait} ثانية...")
                time.sleep(wait)
            else:
                print_log(f"⚠️ خطأ كتابة: {e}")
                return False
    return False

def clean_number(value):
    if not value: return 0
    clean = ''.join(c for c in str(value) if c.isdigit() or c == '.')
    try:
        return float(clean)
    except:
        return 0

def safe_date_str(val):
    if not val: return ""
    if isinstance(val, (datetime, date)):
        return val.strftime('%Y-%m-%d')
    return str(val).split(' ')[0]

def safe_str(val):
    return str(val) if val is not None else ""

def clean_phone_strict(phone_str):
    if not phone_str: return ""
    clean = re.sub(r'\D', '', str(phone_str))
    return clean

def safe_cut(text, length):
    if not text: return ""
    text_str = str(text)
    if len(text_str) > length:
        return text_str[:length]
    return text_str

# =======================================================
# دوال التعامل مع SQL
# =======================================================
def get_next_id(cursor, table_name, id_column):
    try:
        cursor.execute(f"SELECT MAX(CAST({id_column} AS INT)) FROM {table_name}")
        row = cursor.fetchone()
        return (int(row[0]) + 1) if row and row[0] else 1
    except: return 1

def get_id_by_name(cursor, table, id_col, name_col, name_value):
    if not name_value: return None
    try:
        cursor.execute(f"SELECT TOP 1 {id_col} FROM {table} WHERE {name_col} LIKE ?", (f"%{name_value}%",))
        row = cursor.fetchone()
        return row[0] if row else None
    except: return None

def get_driver_id_by_phone(cursor, phone):
    if not phone: return None
    try:
        cursor.execute("SELECT TOP 1 ID_Driver FROM Drivers_TB WHERE Mobile_num LIKE ?", (f"%{phone}%",))
        row = cursor.fetchone()
        return row[0] if row else None
    except: return None

# =======================================================
# دالة المزامنة العكسية (تحديث الأرشيف)
# =======================================================
def sync_sql_to_google_sheet(cursor, client):
    try:
        sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4/edit')
        try:
            worksheet_db = sheet.worksheet("قاعدة بيانات الحجوزات")
        except:
            worksheet_db = sheet.add_worksheet(title="قاعدة بيانات الحجوزات", rows="10000", cols="25")

        query = """
        SELECT 
            R.Start_Date, R.Start_Clock, 
            C.Name_Customer, C.Mobile_num, 
            R.Release, R.Arrive_Address, 
            R.Customer_Count, R.Bags_Count, 
            Car.Plate_Number, 
            R.Car_Type, 
            R.Collection_Amount, 
            R.note, 
            R.Pay_Method, 
            R.Resv_Man, 
            R.ID_Resvition,
            D.Name_Driver, 
            D.Mobile_num
        FROM Resvition R
        LEFT JOIN Customers_TB C ON R.ID_Customer = C.ID_Customer
        LEFT JOIN Drivers_TB D ON R.ID_Driver = D.ID_Driver
        LEFT JOIN Car_TB Car ON R.ID_Car = Car.ID_Car
        ORDER BY R.Start_Date DESC, R.Start_Clock DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        data_to_upload = []
        headers = ["التاريخ", "الوقت", "العميل", "هاتف العميل", "من", "إلى", "ركاب", "شنط", "السيارة", "النوع", "السعر", "ملاحظات", "الدفع", "الموظف", "SQL_ID", "السائق", "رقم السائق"]
        data_to_upload.append(headers)

        for r in rows:
            row_data = [
                safe_date_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3]), safe_str(r[4]), 
                safe_str(r[5]), safe_str(r[6]), safe_str(r[7]), safe_str(r[8]), safe_str(r[9]), 
                float(r[10]) if r[10] else 0, safe_str(r[11]), safe_str(r[12]), safe_str(r[13]), 
                safe_str(r[14]), safe_str(r[15]), safe_str(r[16])
            ]
            data_to_upload.append(row_data)

        if len(data_to_upload) > 1:
            worksheet_db.clear()
            worksheet_db.update(data_to_upload)
            print_log(f"🔄 تم تحديث الأرشيف بـ {len(data_to_upload)-1} رحلة (الأحدث في الأعلى).")
            
    except Exception as e:
        print_log(f"⚠️ تحذير: فشل تحديث الأرشيف: {e}")

# =======================================================
# البرنامج الرئيسي (V30 - Safe Mode Complete)
# =======================================================
print("\n" + "="*60)
print("   نظام إدارة الحجوزات (V30) - Safe & Comprehensive   ")
print("   ✅ يدعم: إضافة، تعديل، حذف يدوي، إعادة ترحيل، أرشيف   ")
print("   🛑 آمن: لا يمسح البيانات تلقائياً   ")
print("="*60 + "\n")

while True:
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4/edit')
        worksheet_source = sheet.worksheet("امر حجز عميل")
        
        try: sheet_customers_archive = sheet.worksheet("قاعدة بيانات العملاء")
        except: sheet_customers_archive = None

        # ── اقرأ اسم السيرفر من المتغيرات البيئية لو متاح ──
        SERVER_NAME   = os.getenv('SQL_SERVER',   r'WIN-MN41K0F5B2V\SQLEXPRESS')
        DATABASE_NAME = os.getenv('SQL_DATABASE', 'Safety_Drive')
        SQL_USER      = os.getenv('SQL_USER',     '')
        SQL_PASS      = os.getenv('SQL_PASS',     '')

        if SQL_USER and SQL_PASS:
            conn_str = (
                f'Driver={{SQL Server}};Server={SERVER_NAME};'
                f'Database={DATABASE_NAME};'
                f'UID={SQL_USER};PWD={SQL_PASS};'
            )
        else:
            conn_str = (
                f'Driver={{SQL Server}};Server={SERVER_NAME};'
                f'Database={DATABASE_NAME};Trusted_Connection=yes;'
            )

        print_log(f"🔌 جاري الاتصال بـ: {SERVER_NAME} → {DATABASE_NAME}")
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        conn.autocommit = True

        # === تشخيص أحجام الأعمدة (مرة واحدة فقط) ===
        if not globals().get('_cols_printed'):
            print_log("🔍 أحجام أعمدة جدول Resvition:")
            cursor.execute("""
                SELECT c.name, t.name as type_name, c.max_length
                FROM sys.columns c
                JOIN sys.types t ON c.user_type_id = t.user_type_id
                WHERE c.object_id = OBJECT_ID('Resvition')
                ORDER BY c.column_id
            """)
            for r in cursor.fetchall():
                size = r[2] if r[1] not in ('nvarchar','nchar') else r[2]//2
                print(f"   {r[0]}: {r[1]}(max={size})")
            globals()['_cols_printed'] = True
        # ============================================


        all_values = worksheet_source.get_all_values()
        _sheet_batch = []  # تجميع كل التحديثات هنا

        def queue_update(row_idx, col_num, value):
            """يضيف تحديث للقائمة بدل الكتابة الفورية"""
            # تحويل رقم العمود لحرف (A=1, B=2... T=20, U=21)
            col_letter = chr(64 + col_num) if col_num <= 26 else 'A' + chr(64 + col_num - 26)
            _sheet_batch.append({
                'range': f'{col_letter}{row_idx}',
                'values': [[value]]
            })

        def flush_batch():
            """يرسل كل التحديثات المجمعة في call واحدة"""
            if not _sheet_batch:
                return
            try:
                worksheet_source.batch_update(_sheet_batch, value_input_option='RAW')
                print_log(f"📤 batch update: {len(_sheet_batch)} خلية في call واحدة")
                _sheet_batch.clear()
            except Exception as e:
                if '429' in str(e):
                    print_log("⏳ Rate limit في batch - انتظار 30 ثانية...")
                    time.sleep(30)
                    try:
                        worksheet_source.batch_update(_sheet_batch, value_input_option='RAW')
                        _sheet_batch.clear()
                    except: pass
                else:
                    print_log(f"⚠️ batch error: {e}")

        if len(all_values) > 1:
            data_rows = all_values[1:] 
            for i, row in enumerate(data_rows):
                real_row_index = i + 2
                if not row or not any(row): continue
                while len(row) < 24: row.append("")

                status_col = str(row[19]).strip() 
                sql_id_col = str(row[20]).strip()

                # ==================================================
                # 1. تسجيل جديد (فارغ، pending، أو تم الارسال)
                # ==================================================
                if status_col in ["", "pending", "تم الارسال"]:
                    print_log(f"📥 استلام طلب جديد (صف {real_row_index})...")
                    
                    trip_date = safe_cut(row[1], 50); trip_time = safe_cut(row[2], 20)
                    cust_name = safe_cut(row[3], 90)
                    cust_phone = safe_cut(clean_phone_strict(row[4]), 20)
                    cust_whatsapp = safe_cut(row[5], 20)
                    pickup = safe_cut(row[6], 200); dropoff = safe_cut(row[7], 200)
                    pax = clean_number(row[8]); bags = clean_number(row[9])
                    car_name = safe_cut(row[10], 10)
                    cust_status = row[11]; cost = clean_number(row[12])
                    email = safe_cut(row[13], 100); notes = safe_cut(row[15], 500)
                    resv_man = safe_cut(row[17], 50); ticket_img = safe_cut(row[18], 500)

                    # التحقق من صحة البيانات الأساسية
                    if not trip_date or not cust_phone:
                        print_log(f"   ⚠️ صف {real_row_index}: بيانات ناقصة (تاريخ أو هاتف) - تخطّي")
                        queue_update(real_row_index, 20, "بيانات ناقصة")
                        continue

                    car_id = get_id_by_name(cursor, "Car_TB", "ID_Car", "Plate_Number", car_name)
                    
                    # إيجاد أو إنشاء العميل
                    cust_id = None
                    cursor.execute("SELECT ID_Customer FROM Customers_TB WHERE Mobile_num = ?", (cust_phone,))
                    res = cursor.fetchone()
                    
                    if res:
                        cust_id = res[0]
                        print(f"   >> 👤 عميل موجود (ID: {cust_id})")
                    else:
                        try:
                            cust_id = get_next_id(cursor, "Customers_TB", "ID_Customer")
                            cursor.execute("INSERT INTO Customers_TB (ID_Customer, Name_Customer, Mobile_num, WhatsApp_Num, Email) VALUES (?, ?, ?, ?, ?)", (cust_id, cust_name, cust_phone, cust_whatsapp, email))
                            conn.commit()
                            print(f"   >> 👤 عميل جديد تم إنشاؤه (ID: {cust_id})")
                            if sheet_customers_archive:
                                try: sheet_customers_archive.append_row([cust_id, cust_name, cust_phone, cust_whatsapp, email, cust_status, pickup, dropoff, car_name, cost, datetime.now().strftime('%Y-%m-%d')])
                                except: pass
                        except Exception as cust_err:
                            print_log(f"   ⚠️ فشل إنشاء عميل: {cust_err}")

                    if cust_id:
                        new_id = get_next_id(cursor, "Resvition", "ID_Resvition")
                        try:
                            cursor.execute("""
                                INSERT INTO Resvition (ID_Resvition, Start_Date, Start_Clock, Release, Arrive_Address, Car_Type, Customer_Count, Bags_Count, Collection_Amount, Pay_Method, note, ID_Customer, ID_Driver, ID_Office, ID_Car, Ticket_Image_URL, Resv_Man) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (new_id, trip_date, trip_time, pickup, dropoff, car_name, pax, bags, cost, "كاش", notes, cust_id, None, None, car_id, ticket_img, resv_man))
                            conn.commit()
                            queue_update(real_row_index, 20, "تم الترحيل")
                            queue_update(real_row_index, 21, str(new_id))
                            print(f"   >> ✅ تم الحفظ بنجاح (ID: {new_id})")
                            last_full_sync_time = 0
                        except Exception as insert_err:
                            print_log(f"❌ خطأ في إدراج الرحلة - تفاصيل:")
                            print(f"   trip_date='{trip_date}' ({len(str(trip_date))})")
                            print(f"   trip_time='{trip_time}' ({len(str(trip_time))})")
                            print(f"   pickup='{pickup}' ({len(str(pickup))})")
                            print(f"   dropoff='{dropoff}' ({len(str(dropoff))})")
                            print(f"   car_name='{car_name}' ({len(str(car_name))})")
                            print(f"   notes='{notes}' ({len(str(notes))})")
                            print(f"   resv_man='{resv_man}' ({len(str(resv_man))})")
                            print(f"   ticket_img='{ticket_img}' ({len(str(ticket_img))})")
                            print(f"   الخطأ: {insert_err}")
                            # محاولة ثانية مع تقليص أقصى لجميع الحقول
                            try:
                                print_log(f"   🔄 محاولة ثانية مع تقليص مشدد...")
                                cursor.execute("""
                                    INSERT INTO Resvition (ID_Resvition, Start_Date, Start_Clock, Release, Arrive_Address, Car_Type, Customer_Count, Bags_Count, Collection_Amount, Pay_Method, note, ID_Customer, ID_Driver, ID_Office, ID_Car, Ticket_Image_URL, Resv_Man) 
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (new_id,
                                      safe_cut(trip_date, 10),
                                      safe_cut(trip_time, 8),
                                      safe_cut(pickup, 50),
                                      safe_cut(dropoff, 50),
                                      safe_cut(car_name, 10),
                                      pax, bags, cost,
                                      safe_cut("كاش", 10),
                                      safe_cut(notes, 50),
                                      cust_id, None, None, car_id,
                                      safe_cut(ticket_img, 50),
                                      safe_cut(resv_man, 30)))
                                conn.commit()
                                queue_update(real_row_index, 20, "تم الترحيل")
                                queue_update(real_row_index, 21, str(new_id))
                                print(f"   >> ✅ تم الحفظ بنجاح في المحاولة الثانية (ID: {new_id})")
                                last_full_sync_time = 0
                            except Exception as retry_err:
                                print(f"   >> ❌ فشل المحاولة الثانية: {retry_err}")
                                queue_update(real_row_index, 20, "خطأ في الإدراج")
                    else:
                        print_log(f"   ❌ فشل الحصول على cust_id للصف {real_row_index}")
                        queue_update(real_row_index, 20, "خطأ: فشل العميل")

                # ==================================================
                # 2. تعديل
                # ==================================================
                elif status_col == "تعديل" and sql_id_col:
                    print_log(f"🔄 تعديل رحلة {sql_id_col}...")
                    cost = clean_number(row[12])
                    notes = safe_cut(row[14], 200)
                    driver_name_new = row[21]; driver_phone_new = row[22]
                    
                    driver_id = None
                    if driver_name_new: driver_id = get_id_by_name(cursor, "Drivers_TB", "ID_Driver", "Name_Driver", driver_name_new)
                    if not driver_id and driver_phone_new: driver_id = get_driver_id_by_phone(cursor, clean_phone_strict(driver_phone_new))
                    
                    if driver_id:
                        cursor.execute("UPDATE Resvition SET Start_Date=?, Start_Clock=?, Release=?, Arrive_Address=?, Car_Type=?, Collection_Amount=?, note=?, ID_Driver=? WHERE ID_Resvition = ?", (row[1], row[2], row[6], row[7], row[10], cost, notes, driver_id, sql_id_col))
                    else:
                        cursor.execute("UPDATE Resvition SET Start_Date=?, Start_Clock=?, Release=?, Arrive_Address=?, Car_Type=?, Collection_Amount=?, note=? WHERE ID_Resvition = ?", (row[1], row[2], row[6], row[7], row[10], cost, notes, sql_id_col))
                    conn.commit()
                    queue_update(real_row_index, 20, "تم الترحيل")
                    last_full_sync_time = 0

                # ==================================================
                # 3. حذف (يدوي فقط - آمن)
                # ==================================================
                elif status_col == "حذف" and sql_id_col:
                     print_log(f"🗑️ تنفيذ طلب حذف الرحلة {sql_id_col}...")
                     cursor.execute("DELETE FROM Resvition WHERE ID_Resvition = ?", (sql_id_col,))
                     conn.commit()
                     queue_update(real_row_index, 20, "تم الحذف")
                     last_full_sync_time = 0

                # ==================================================
                # 4. إعادة ترحيل (كاملة)
                # ==================================================
                elif status_col == "إعادة ترحيل":
                    print_log(f"♻️ إعادة ترحيل الرحلة للصف {real_row_index}...")
                    
                    trip_date = safe_cut(row[1], 50); trip_time = safe_cut(row[2], 20)
                    cust_name = safe_cut(row[3], 90)
                    cust_phone = safe_cut(clean_phone_strict(row[4]), 20)
                    cust_whatsapp = safe_cut(row[5], 20)
                    pickup = safe_cut(row[6], 200); dropoff = safe_cut(row[7], 200)
                    pax = clean_number(row[8]); bags = clean_number(row[9])
                    car_name = safe_cut(row[10], 10)
                    cost = clean_number(row[12])
                    email = safe_cut(row[13], 100); notes = safe_cut(row[14], 500)
                    resv_man = safe_cut(row[17], 50); ticket_img = safe_cut(row[18], 500)

                    car_id = get_id_by_name(cursor, "Car_TB", "ID_Car", "Plate_Number", car_name)
                    
                    # العميل
                    cust_id = None
                    cursor.execute("SELECT ID_Customer FROM Customers_TB WHERE Mobile_num = ?", (cust_phone,))
                    res = cursor.fetchone()
                    if res:
                        cust_id = res[0]
                    else:
                        try:
                            cust_id = get_next_id(cursor, "Customers_TB", "ID_Customer")
                            cursor.execute("INSERT INTO Customers_TB (ID_Customer, Name_Customer, Mobile_num, WhatsApp_Num, Email) VALUES (?, ?, ?, ?, ?)", (cust_id, cust_name, cust_phone, cust_whatsapp, email))
                            conn.commit()
                        except: pass

                    if cust_id:
                        new_id = get_next_id(cursor, "Resvition", "ID_Resvition")
                        cursor.execute("""
                            INSERT INTO Resvition (ID_Resvition, Start_Date, Start_Clock, Release, Arrive_Address, Car_Type, Customer_Count, Bags_Count, Collection_Amount, Pay_Method, note, ID_Customer, ID_Driver, ID_Office, ID_Car, Ticket_Image_URL, Resv_Man) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (new_id, trip_date, trip_time, pickup, dropoff, car_name, pax, bags, cost, "كاش", notes, cust_id, None, None, car_id, ticket_img, resv_man))
                        conn.commit()
                        queue_update(real_row_index, 20, "تم الترحيل")
                        queue_update(real_row_index, 21, str(new_id))
                        print(f"   >> ✅ تم إعادة الترحيل بنجاح (ID: {new_id})")
                        last_full_sync_time = 0

                # ==================================================
                # 5. استعادة الرحلات المفقودة (batch - لتقليل API calls)
                # ==================================================
                elif status_col == "تم الترحيل" and sql_id_col:
                    try:
                        cursor.execute("SELECT count(*) FROM Resvition WHERE ID_Resvition = ?", (sql_id_col,))
                        if cursor.fetchone()[0] == 0:
                            queue_update(real_row_index, 20, "إعادة ترحيل")
                            print_log(f"📌 مجدول للاستعادة: {sql_id_col}")
                    except: pass

        # ── إرسال كل التحديثات في batch واحدة ──
        flush_batch()

        # ===================================================
        # 🔄 التزامن العكسي: SQL Server → الشيت (السائق)
        # لو السائق اتعيّن في النظام الداخلي ومش موجود في الشيت،
        # بنكتبه في العمود 22 و23 لتفعيل إرسال رسائل الأتمتة
        # ===================================================
        try:
            driver_sync_batch = []
            re_read_rows = worksheet_source.get_all_values()
            re_data_rows = re_read_rows[1:] if len(re_read_rows) > 1 else []

            for ri, rrow in enumerate(re_data_rows):
                real_ri = ri + 2
                while len(rrow) < 24: rrow.append("")
                sql_id_val = str(rrow[20]).strip()
                sheet_driver_name = str(rrow[21]).strip()
                sheet_driver_phone = str(rrow[22]).strip()

                # فقط الصفوف التي لها SQL_ID ولا يوجد بها سائق في الشيت
                if not sql_id_val or not sql_id_val.isdigit(): continue
                if sheet_driver_name:  continue  # السائق موجود بالفعل

                try:
                    cursor.execute("""
                        SELECT D.Name_Driver, D.Mobile_num
                        FROM Resvition R
                        LEFT JOIN Drivers_TB D ON R.ID_Driver = D.ID_Driver
                        WHERE R.ID_Resvition = ? AND R.ID_Driver IS NOT NULL
                    """, (sql_id_val,))
                    dr = cursor.fetchone()
                    if dr and dr[0]:
                        db_driver_name = str(dr[0]).strip()
                        db_driver_phone = str(dr[1] or "").strip()
                        if db_driver_name:
                            col_letter_22 = 'V'  # عمود 22
                            col_letter_23 = 'W'  # عمود 23
                            driver_sync_batch.append({'range': f'{col_letter_22}{real_ri}', 'values': [[db_driver_name]]})
                            if db_driver_phone:
                                driver_sync_batch.append({'range': f'{col_letter_23}{real_ri}', 'values': [[db_driver_phone]]})
                            print_log(f"🚕 [DriverSync] صف {real_ri}: كتابة السائق '{db_driver_name}' من SQL Server → الشيت")
                except Exception as de:
                    pass

            if driver_sync_batch:
                try:
                    worksheet_source.batch_update(driver_sync_batch, value_input_option='RAW')
                    print_log(f"✅ [DriverSync] تم تحديث {len(driver_sync_batch)} خلية (بيانات السائقين)")
                except Exception as be:
                    print_log(f"⚠️ [DriverSync] خطأ في batch update: {be}")
        except Exception as ds_err:
            print_log(f"⚠️ [DriverSync] خطأ عام: {ds_err}")


        # ===================================================
        # تحديث الأرشيف (كل 5 دقائق)
        # ===================================================
        current_time = time.time()
        if (current_time - last_full_sync_time) > FULL_SYNC_INTERVAL:
            print_log("♻️ بدء تحديث الأرشيف...")
            sync_sql_to_google_sheet(cursor, client)
            last_full_sync_time = current_time

        conn.close()
        time.sleep(20)

    except Exception as e:
        err_str = str(e)
        if '429' in err_str or 'Quota exceeded' in err_str:
            print_log("⏳ [حد أقتباس Google Sheets] تم الوصول للحد الأقصى لطلبات جوجل شيت (429). جاري التوقف المؤقت لمدة 45 ثانية لتصفير الحصة...")
            time.sleep(45)
        else:
            print(f"\n❌ خطأ عام: {e}")
            print("⏳ إعادة المحاولة خلال 10 ثواني...")
            time.sleep(10)