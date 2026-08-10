import inspect_trips
import json

res = inspect_trips.query_supabase('profiles', {'phone': 'like.*1070819859*'})
print("Profile with 1070819859:")
print(json.dumps(res, ensure_ascii=False, indent=2))
