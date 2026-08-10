import inspect_trips
import json

res = inspect_trips.query_supabase('profiles', {'role': 'eq.client', 'limit': '5'})
print(json.dumps(res, ensure_ascii=False, indent=2))
