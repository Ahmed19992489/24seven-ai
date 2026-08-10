import inspect_trips
import json

# Check مؤمن's google_reservations
print("=== Google Reservations for 01070819859 ===")
res = inspect_trips.query_supabase('google_reservations', {'customer_phone': 'ilike.%1070819859%'})
print(json.dumps(res, ensure_ascii=False, indent=2))

print("\n=== Google Reservations for مومن ===")
res2 = inspect_trips.query_supabase('google_reservations', {'customer_name': 'ilike.%مؤمن%'})
print(json.dumps(res2, ensure_ascii=False, indent=2))

print("\n=== Trips where user_id = 1c5aeb93 ===")
res3 = inspect_trips.query_supabase('trips', {'user_id': 'eq.1c5aeb93-6601-4f18-9246-8ce42a6e12fd'})
print(json.dumps(res3, ensure_ascii=False, indent=2))

print("\n=== Profile 1c5aeb93 with email ===")
res4 = inspect_trips.query_supabase('profiles', {'id': 'eq.1c5aeb93-6601-4f18-9246-8ce42a6e12fd'})
print(json.dumps(res4, ensure_ascii=False, indent=2))
