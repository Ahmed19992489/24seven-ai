import inspect_trips
import json

res = inspect_trips.query_supabase('profiles', {'email': 'like.*1070819859*'})
print(json.dumps(res, ensure_ascii=False, indent=2))
