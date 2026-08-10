import inspect_trips
import json

res = inspect_trips.query_supabase('google_reservations', {'customer_phone': 'like.*1070819859*'})
for r in res:
    print(f"ID: {r.get('id')}, Phone: {r.get('customer_phone')}")
