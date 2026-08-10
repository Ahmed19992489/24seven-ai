import inspect_trips

res = inspect_trips.query_supabase('profiles', {'full_name': 'eq.عميل جوجل', 'order': 'created_at.desc', 'limit': '5'})
print(res)
