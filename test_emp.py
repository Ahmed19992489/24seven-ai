import inspect_trips
res = inspect_trips.query_supabase('google_reservations', {'customer_name': 'eq.مؤمن', 'order': 'created_at.desc', 'limit': '5'})
for r in res:
    print(f"ID: {r.get('id')}, booking_employee: {r.get('booking_employee')}")
