import inspect_trips
import json

try:
    res = inspect_trips.query_supabase('profiles', {'id': 'eq.1c5aeb93-6601-4f18-9246-8ce42a6e12fd'})
    print("Before:", res)
    
    # Try to upsert
    from supabase import create_client, Client
    import os
    url = "https://khskudtxbypohvnreloi.supabase.co"
    key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I"
    supabase: Client = create_client(url, key)
    
    data = supabase.table("profiles").upsert({
        "id": "1c5aeb93-6601-4f18-9246-8ce42a6e12fd",
        "phone": "01070819859",
        "full_name": "مؤمن",
        "wallet_balance": 0
    }).execute()
    print("After:", data)
except Exception as e:
    print("Error:", e)
