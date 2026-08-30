import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import os
import re
import requests
import json
import hashlib

current_dir = os.path.dirname(os.path.abspath(__file__))
creds_path = os.path.join(current_dir, 'credentials.json')
if not os.path.exists(creds_path):
    creds_path = os.path.join(r"c:\Users\pc2\Downloads\New folder (2)", 'credentials.json')

SHEET_URL = 'https://docs.google.com/spreadsheets/d/1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4/edit'
SHEET_NAME = 'امر حجز عميل'

NEON_CONN_STR = os.getenv("DATABASE_URL") or "postgresql://neondb_owner:npg_VM4tSBwN5PGd@ep-plain-rice-auzortld-pooler.c-10.us-east-1.aws.neon.tech/neondb?sslmode=require"
NEON_HTTP_URL = "https://ep-plain-rice-auzortld-pooler.c-10.us-east-1.aws.neon.tech/sql"

SYNC_INTERVAL = 60  # ثانية
FULL_SYNC_EVERY = 30  # مزامنة كاملة كل 30 دورة (30 دقيقة)

def print_log(msg):
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=True)

def safe_str(val):
    return str(val).strip() if val is not None else ""

def safe_num(val):
    try:
        return float(str(val).replace(',', '').strip()) if val else 0
    except:
        return 0

def clean_phone(phone_str):
    return re.sub(r'\D', '', str(phone_str)) if phone_str else ""

def clean_date(val):
    if not val: return None
    try:
        val = str(val).strip()
        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%m-%d-%Y']:
            try:
                return datetime.strptime(val.split(' ')[0], fmt).strftime('%Y-%m-%d')
            except:
                pass
    except:
        pass
    return None

def execute_neon(sql, params=[]):
    for attempt in range(3):
        try:
            r = requests.post(
                NEON_HTTP_URL,
                headers={"Neon-Connection-String": NEON_CONN_STR},
                json={"query": sql, "params": params},
                timeout=20
            )
            if r.status_code == 200:
                return r.json()
            else:
                print_log(f"⚠️ Neon API Error {r.status_code}: {r.text[:120]}")
        except Exception as e:
            print_log(f"⚠️ Neon Request Exception ({attempt+1}/3): {e}")
            time.sleep(2)
    return None

def get_gspread_client():
    for attempt in range(5):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
            client = gspread.authorize(creds)
            sheet = client.open_by_url(SHEET_URL)
            worksheet = sheet.worksheet(SHEET_NAME)
            return worksheet
        except Exception as e:
            print_log(f"⚠️ فشل الاتصال بـ Google Sheets (المحاولة {attempt+1}/5): {e}")
            time.sleep(3)
    return None

def upsert_records_to_neon(records, batch_size=50):
    if not records:
        return 0
    
    total_upserted = 0
    num_cols = 26

    for b_idx in range(0, len(records), batch_size):
        batch = records[b_idx:b_idx + batch_size]
        batch_values = []
        params = []

        for i, rec in enumerate(batch):
            offset = i * num_cols
            p_placeholders = [f"${offset + j + 1}" for j in range(num_cols)]
            batch_values.append(f"({', '.join(p_placeholders)}, NOW())")
            params.extend([
                rec["sheet_row"], rec["trip_date"], rec["trip_time"], rec["customer_name"],
                rec["customer_phone"], rec["whatsapp_num"], rec["pickup_address"], rec["dropoff_address"],
                rec["passengers"], rec["bags"], rec["car_type"], rec["cost"], rec["email"],
                rec["notes"], rec["trip_type"], rec["sql_server_id"], rec["booking_employee"],
                rec["status"], rec["modified_driver_name"], rec["modified_driver_phone"],
                rec["driver_msg_status"], rec["confirm_msg_status"], rec["client_decision"],
                rec["location_link"], rec["rating_stars"], rec["trip_status"]
            ])

        sql = f"""
            INSERT INTO google_reservations (
                sheet_row, trip_date, trip_time, customer_name, customer_phone, whatsapp_num,
                pickup_address, dropoff_address, passengers, bags, car_type, cost, email, notes,
                trip_type, sql_server_id, booking_employee, status, modified_driver_name,
                modified_driver_phone, driver_msg_status, confirm_msg_status, client_decision,
                location_link, rating_stars, trip_status, updated_at
            ) VALUES {', '.join(batch_values)}
            ON CONFLICT (sheet_row) DO UPDATE SET
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
                cost = EXCLUDED.cost,
                notes = EXCLUDED.notes,
                status = CASE WHEN google_reservations.status = 'driver_assigned' AND (EXCLUDED.status IS NULL OR EXCLUDED.status = 'pending') THEN google_reservations.status ELSE EXCLUDED.status END,
                modified_driver_name = COALESCE(NULLIF(EXCLUDED.modified_driver_name, ''), google_reservations.modified_driver_name),
                modified_driver_phone = COALESCE(NULLIF(EXCLUDED.modified_driver_phone, ''), google_reservations.modified_driver_phone),
                driver_msg_status = EXCLUDED.driver_msg_status,
                confirm_msg_status = EXCLUDED.confirm_msg_status,
                client_decision = EXCLUDED.client_decision,
                trip_status = EXCLUDED.trip_status,
                updated_at = NOW();
        """

        res = execute_neon(sql, params)
        if res is not None:
            total_upserted += len(batch)

    return total_upserted

def main_loop():
    print("\n" + "="*60, flush=True)
    print("   🚀 مزامنة Google Sheet ↔ Neon Postgres فائقة السرعة   ", flush=True)
    print("   يعمل بشكل تلقائي ومستمر بدون أي حظر أو توقف   ", flush=True)
    print("="*60 + "\n", flush=True)

    _sync_cycle_count = 0
    _row_fingerprints = {}

    while True:
        try:
            _sync_cycle_count += 1
            is_full = (_sync_cycle_count % FULL_SYNC_EVERY == 1)
            cycle_label = "كاملة" if is_full else "ذكية (التغييرات الجديدة)"
            print_log(f"🚀 بدء دورة مزامنة {cycle_label} (#{_sync_cycle_count})...")

            worksheet = get_gspread_client()
            if not worksheet:
                print_log("❌ تعذر الاتصال بـ Google Sheets. إعادة المحاولة في الدورة القادمة...")
                time.sleep(SYNC_INTERVAL)
                continue

            all_values = []
            for attempt in range(3):
                try:
                    all_values = worksheet.get_all_values()
                    break
                except Exception as e_sheet:
                    print_log(f"⚠️ خطأ قراءة الشيت ({attempt+1}/3): {e_sheet}")
                    time.sleep(2)

            if len(all_values) < 2:
                print_log("⚠️ الشيت فارغ أو يحتوي على عناوين فقط.")
                time.sleep(SYNC_INTERVAL)
                continue

            data_rows = all_values[1:]
            records_to_upsert = []

            for i, row in enumerate(data_rows):
                real_row_index = i + 2
                if not row or not any(row):
                    continue
                while len(row) < 35:
                    row.append("")

                trip_date = clean_date(row[1]) or safe_str(row[1])
                trip_time = safe_str(row[2])
                customer_name = safe_str(row[3])
                customer_phone = safe_str(row[4])
                whatsapp_num = safe_str(row[5]) or customer_phone
                pickup_address = safe_str(row[6])
                dropoff_address = safe_str(row[7])
                passengers = safe_num(row[8]) or 1
                bags = safe_num(row[9]) or 0
                car_type = safe_str(row[10]) or 'سيدان'
                cost = safe_num(row[12])
                email = safe_str(row[13])
                notes = safe_str(row[14])
                trip_type = safe_str(row[15]) or 'ذهاب فقط'
                sql_server_id = safe_str(row[16]) or safe_str(row[20])
                booking_employee = safe_str(row[17])
                status = safe_str(row[19]) or 'pending'
                modified_driver_name = safe_str(row[21])
                modified_driver_phone = safe_str(row[22])
                driver_msg_status = safe_str(row[24])
                confirm_msg_status = safe_str(row[26])
                client_decision = safe_str(row[27])
                location_link = safe_str(row[28])
                rating_stars = safe_num(row[29])
                trip_status = safe_str(row[34])

                if not customer_name and not customer_phone and not pickup_address:
                    continue

                # حساب بصمة التغيير لتسريع الدورات المتتالية
                row_raw_str = f"{trip_date}|{trip_time}|{customer_name}|{customer_phone}|{pickup_address}|{dropoff_address}|{cost}|{status}|{modified_driver_name}|{modified_driver_phone}|{driver_msg_status}|{confirm_msg_status}|{client_decision}|{trip_status}"
                row_hash = hashlib.md5(row_raw_str.encode('utf-8')).hexdigest()

                if not is_full and _row_fingerprints.get(real_row_index) == row_hash:
                    continue  # لم يتغير الصف — تخطيه لتوفير الموارد والوقت

                _row_fingerprints[real_row_index] = row_hash

                records_to_upsert.append({
                    "sheet_row": real_row_index,
                    "trip_date": trip_date,
                    "trip_time": trip_time,
                    "customer_name": customer_name,
                    "customer_phone": customer_phone,
                    "whatsapp_num": whatsapp_num,
                    "pickup_address": pickup_address,
                    "dropoff_address": dropoff_address,
                    "passengers": int(passengers),
                    "bags": int(bags),
                    "car_type": car_type,
                    "cost": cost,
                    "email": email,
                    "notes": notes,
                    "trip_type": trip_type,
                    "sql_server_id": sql_server_id,
                    "booking_employee": booking_employee,
                    "status": status,
                    "modified_driver_name": modified_driver_name,
                    "modified_driver_phone": modified_driver_phone,
                    "driver_msg_status": driver_msg_status,
                    "confirm_msg_status": confirm_msg_status,
                    "client_decision": client_decision,
                    "location_link": location_link,
                    "rating_stars": rating_stars,
                    "trip_status": trip_status
                })

            t0 = time.time()
            if records_to_upsert:
                upserted_count = upsert_records_to_neon(records_to_upsert, batch_size=50)
                print_log(f"✅ تم مزامنة {upserted_count} حجز بنجاح في Neon Postgres (استغرق {time.time()-t0:.2f} ثانية)!")
            else:
                print_log("⚡ لا توجد تعديلات جديدة في الشيت — البيانات متزامنة بنسبة 100% (0.00 ثانية).")

        except Exception as e_main:
            print_log(f"❌ خطأ غير متوقع: {e_main}")

        print_log(f"⏳ انتظار {SYNC_INTERVAL} ثانية للدورة القادمة...\n----------------------------------------")
        time.sleep(SYNC_INTERVAL)

if __name__ == '__main__':
    main_loop()
