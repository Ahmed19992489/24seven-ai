import inspect_trips
import json

res = inspect_trips.query_supabase('profiles', {'full_name': 'like.*مؤمن*'})
print(json.dumps(res, ensure_ascii=False, indent=2))
