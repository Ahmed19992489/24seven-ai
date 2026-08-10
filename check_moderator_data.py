"""فحص بيانات الموديتور في قاعدة البيانات"""
import requests
import json

SUPABASE_URL = 'https://khskudtxbypohvnreloi.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I'

headers = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

print("=" * 60)
print("1. أسماء الموظفين في profiles (full_name + role):")
print("=" * 60)
r = requests.get(
    f'{SUPABASE_URL}/rest/v1/profiles',
    params={'select': 'full_name,role,email', 'role': 'in.(moderator,admin,ops)'},
    headers=headers
)
if r.ok:
    profiles = r.json()
    for p in profiles:
        print(f"  - full_name: '{p.get('full_name')}' | role: '{p.get('role')}'")
else:
    # Try without filter
    r2 = requests.get(
        f'{SUPABASE_URL}/rest/v1/profiles',
        params={'select': 'full_name,role', 'limit': '50'},
        headers=headers
    )
    if r2.ok:
        for p in r2.json():
            if p.get('role') in ['moderator', 'admin', 'ops', None]:
                print(f"  - full_name: '{p.get('full_name')}' | role: '{p.get('role')}'")

print()
print("=" * 60)
print("2. أسماء booking_employee في google_reservations (مميزة):")
print("=" * 60)
r2 = requests.get(
    f'{SUPABASE_URL}/rest/v1/google_reservations',
    params={'select': 'booking_employee', 'booking_employee': 'not.is.null', 'limit': '500'},
    headers=headers
)
if r2.ok:
    data = r2.json()
    names = set(d.get('booking_employee', '') for d in data if d.get('booking_employee'))
    for name in sorted(names):
        print(f"  - '{name}'")
    print(f"\n  المجموع: {len(names)} اسم مميز")
else:
    print("خطأ:", r2.text[:200])

print()
print("=" * 60)
print("3. عدد حجوزات اليوم في قاعدة البيانات:")
print("=" * 60)
from datetime import date
today = str(date.today())
r3 = requests.get(
    f'{SUPABASE_URL}/rest/v1/google_reservations',
    params={'select': 'count', 'trip_date': f'eq.{today}'},
    headers={**headers, 'Prefer': 'count=exact'},
)
print(f"  رحلات اليوم ({today}): {r3.headers.get('Content-Range', 'غير محدد')}")

# Also try trips table
r4 = requests.get(
    f'{SUPABASE_URL}/rest/v1/trips',
    params={'select': 'count', 'limit': '1'},
    headers={**headers, 'Prefer': 'count=exact'},
)
print(f"  رحلات في trips table: {r4.headers.get('Content-Range', 'غير محدد')}")
