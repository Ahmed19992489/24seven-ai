import inspect_trips
import json

res = inspect_trips.query_supabase('profiles', {'id': 'eq.1c5aeb93-6601-4f18-9246-8ce42a6e12fd'})
print(json.dumps(res, ensure_ascii=False, indent=2))
