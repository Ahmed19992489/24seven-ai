import inspect_trips
import json

# Check مؤمن's profile - phone 01070819859
print("=== Profile for 01070819859 ===")
res = inspect_trips.query_supabase('profiles', {'phone': 'eq.01070819859'})
print(json.dumps(res, ensure_ascii=False, indent=2))

print("\n=== Trips with client_phone 01070819859 ===")
res2 = inspect_trips.query_supabase('trips', {'client_phone': 'eq.01070819859'})
print(json.dumps(res2, ensure_ascii=False, indent=2))

print("\n=== Trips with client_phone 1070819859 ===")
res3 = inspect_trips.query_supabase('trips', {'client_phone': 'eq.1070819859'})
print(json.dumps(res3, ensure_ascii=False, indent=2))

print("\n=== Trips ilike admin_notes 01070819859 ===")
res4 = inspect_trips.query_supabase('trips', {'admin_notes': 'ilike.%01070819859%'})
print(json.dumps(res4, ensure_ascii=False, indent=2))
