"""تحقق من تنسيق trip_date وبيانات الرحلات"""
import requests
from datetime import date, datetime

SUPABASE_URL = 'https://khskudtxbypohvnreloi.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I'
headers = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
}

# 1. Get sample of google_reservations to check trip_date format
r = requests.get(
    f'{SUPABASE_URL}/rest/v1/google_reservations',
    params={'select': 'customer_name,trip_date,booking_employee,trip_type', 'limit': '5', 'order': 'created_at.desc'},
    headers=headers
)
print("=== google_reservations sample ===")
if r.ok:
    for row in r.json():
        print(f"  customer: {row.get('customer_name')} | date: '{row.get('trip_date')}' | employee: '{row.get('booking_employee')}' | type: '{row.get('trip_type')}'")

# 2. Get today's reservations
today = str(date.today())
print(f"\n=== Reservations for today ({today}) ===")
r2 = requests.get(
    f'{SUPABASE_URL}/rest/v1/google_reservations',
    params={'select': 'customer_name,trip_date,trip_type', 'trip_date': f'eq.{today}', 'limit': '20'},
    headers=headers
)
if r2.ok:
    data = r2.json()
    print(f"  Count: {len(data)}")
    for row in data[:5]:
        print(f"  - {row.get('customer_name')} | {row.get('trip_date')} | {row.get('trip_type')}")

# 3. Check trips table - what's the date format
r3 = requests.get(
    f'{SUPABASE_URL}/rest/v1/trips',
    params={'select': 'client_name,trip_date,status,created_at', 'limit': '5', 'order': 'created_at.desc'},
    headers=headers
)
print(f"\n=== trips table sample ===")
if r3.ok:
    for row in r3.json():
        print(f"  client: {row.get('client_name')} | trip_date: '{row.get('trip_date')}' | status: '{row.get('status')}'")

# 4. Check all distinct trip_date formats in google_reservations
r4 = requests.get(
    f'{SUPABASE_URL}/rest/v1/google_reservations',
    params={'select': 'trip_date', 'order': 'trip_date.desc', 'limit': '20'},
    headers=headers
)
print(f"\n=== Most recent trip_dates ===")
if r4.ok:
    dates = [row.get('trip_date') for row in r4.json()]
    for d in dates[:10]:
        print(f"  '{d}'")
