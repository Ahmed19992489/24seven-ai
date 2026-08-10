import inspect_trips
import json

res = inspect_trips.query_supabase('profiles', {'role': 'eq.client', 'full_name': 'eq.عميل جوجل'})
print(json.dumps(res, ensure_ascii=False, indent=2))
