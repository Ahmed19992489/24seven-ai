import inspect_trips
import json

res = inspect_trips.query_supabase('google_reservations', {'customer_name': 'eq.مؤمن', 'order': 'created_at.desc', 'limit': '5'})
print('--- google_reservations ---')
if res:
    for r in res:
        print(f"ID: {r.get('id')}, Time: {r.get('trip_time')}, Row: {r.get('sheet_row')}, Created: {r.get('created_at')}, SheetTime: {r.get('sheet_timestamp')}, Phone: {r.get('customer_phone')}")

res2 = inspect_trips.query_supabase('trips', {'manual_client_name': 'eq.مؤمن', 'order': 'created_at.desc', 'limit': '5'})
print('\n--- trips ---')
if res2:
    for r in res2:
        print(f"ID: {r.get('id')}, Notes: {r.get('admin_notes')}")
