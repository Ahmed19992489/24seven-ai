import inspect_trips
res = inspect_trips.query_supabase('profiles', {'phone': 'like.*1070819859*'})
print(res)
