import inspect_trips
import json

# Check trips by sql_server_id 11401 and 11402
print("=== Trip 11401 ===")
res = inspect_trips.query_supabase('trips', {'id': 'eq.11401'})
print(json.dumps(res, ensure_ascii=False, indent=2))

print("\n=== Trip 11402 ===")
res2 = inspect_trips.query_supabase('trips', {'id': 'eq.11402'})
print(json.dumps(res2, ensure_ascii=False, indent=2))

print("\n=== Trips with manual_client_name = مؤمن ===")
res3 = inspect_trips.query_supabase('trips', {'manual_client_name': 'ilike.%مؤمن%'})
print(json.dumps(res3, ensure_ascii=False, indent=2))
