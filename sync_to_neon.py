import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import os
import re
import pg8000.native
import ssl

current_dir = os.path.dirname(os.path.abspath(__file__))
creds_path = os.path.join(current_dir, 'credentials.json')
if not os.path.exists(creds_path):
    creds_path = os.path.join(r"c:\Users\pc2\Downloads\New folder (2)", 'credentials.json')

SHEET_URL = 'https://docs.google.com/spreadsheets/d/1-YglRYU8RZ6fl8xoWBNgxiV5IRna4KgE8ynpjsjtCD4/edit'
SHEET_NAME = 'امر حجز عميل'

NEON_USER = os.getenv("PGUSER", "neondb_owner")
NEON_PASSWORD = os.getenv("PGPASSWORD", "npg_VM4tSBwN5PGd")
NEON_HOST = os.getenv("PGHOST", "ep-plain-rice-auzortld-pooler.c-10.us-east-1.aws.neon.tech")
NEON_DB = os.getenv("PGDATABASE", "neondb")

SYNC_INTERVAL = 60  # ثانية

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

def get_db_con():
    return pg8000.native.Connection(
        user=NEON_USER,
        password=NEON_PASSWORD,
        host=NEON_HOST,
        port=5432,
        database=NEON_DB,
        ssl_context=ssl.create_default_context(),
        timeout=15
    )

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

print("\n" + "="*60)
print("   🚀 مزامنة Google Sheet ↔ Neon Postgres فائقة السرعة   ")
print("   يعمل بشكل تلقائي ومستمر بدون أي حظر أو توقف   ")
print("="*60 + "\n")

_sync_cycle_count = 0

while True:
    try:
        _sync_cycle_count += 1
        print_log(f"🚀 بدء دورة مزامنة Neon Postgres (#{_sync_cycle_count})...")

        worksheet = get_gspread_client()
        if not worksheet:
            print_log("❌ تعذر الاتصال بـ Google Sheets. إعادة المحاولة في الدورة القادمة...")
            time.sleep(SYNC_INTERVAL)
            continue

        con = get_db_con()

        # قراءة كل السطور من Google Sheet
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
            con.close()
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

        # إرسال السجلات إلى Neon Postgres
        upserted_count = 0
        for rec in records_to_upsert:
            con.run("""
                INSERT INTO google_reservations (
                    sheet_row, trip_date, trip_time, customer_name, customer_phone, whatsapp_num,
                    pickup_address, dropoff_address, passengers, bags, car_type, cost, email, notes,
                    trip_type, sql_server_id, booking_employee, status, modified_driver_name,
                    modified_driver_phone, driver_msg_status, confirm_msg_status, client_decision,
                    location_link, rating_stars, trip_status, updated_at
                ) VALUES (
                    :sheet_row, :trip_date, :trip_time, :customer_name, :customer_phone, :whatsapp_num,
                    :pickup_address, :dropoff_address, :passengers, :bags, :car_type, :cost, :email, :notes,
                    :trip_type, :sql_server_id, :booking_employee, :status, :modified_driver_name,
                    :modified_driver_phone, :driver_msg_status, :confirm_msg_status, :client_decision,
                    :location_link, :rating_stars, :trip_status, NOW()
                )
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
                    status = EXCLUDED.status,
                    modified_driver_name = EXCLUDED.modified_driver_name,
                    modified_driver_phone = EXCLUDED.modified_driver_phone,
                    driver_msg_status = EXCLUDED.driver_msg_status,
                    confirm_msg_status = EXCLUDED.confirm_msg_status,
                    client_decision = EXCLUDED.client_decision,
                    trip_status = EXCLUDED.trip_status,
                    updated_at = NOW();
            """, **rec)
            upserted_count += 1

        con.close()
        print_log(f"✅ تم مزامنة {upserted_count} حجز بنجاح في Neon Postgres!")

    except Exception as e_main:
        print_log(f"❌ خطأ في دورة المزامنة: {e_main}")

    print_log(f"⏳ انتظار {SYNC_INTERVAL} ثانية للدورة القادمة...\n----------------------------------------")
    time.sleep(SYNC_INTERVAL)
