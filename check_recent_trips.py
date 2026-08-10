import inspect_trips
import json

# The trips for مؤمن have sql_server_id 11401, 11402 in google_reservations
# But in the trips table they might have different IDs
# Let's look at trips from recent dates and check

print("=== All trips with client_phone containing 70819859 ===")
res = inspect_trips.query_supabase('trips', {'client_phone': 'ilike.%70819859%'})
print(json.dumps(res, ensure_ascii=False, indent=2))

print("\n=== Most recent trips (June 18-19 2026) ===")
import urllib.request, urllib.parse

url = "https://khskudtxbypohvnreloi.supabase.co/rest/v1/"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I"

def query(table, params):
    q = urllib.parse.urlencode(params)
    req_url = f"{url}{table}?{q}"
    req = urllib.request.Request(req_url, headers={
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

res2 = query('trips', {'select': 'id,user_id,client_phone,manual_client_name,created_at,status', 'order': 'id.desc', 'limit': '10'})
print(json.dumps(res2, ensure_ascii=False, indent=2))
