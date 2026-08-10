import inspect_trips
res = inspect_trips.query_supabase('trips', {'client_phone': 'like.*1070819859*'})
print(res)
