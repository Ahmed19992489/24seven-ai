import json
import urllib.request, urllib.parse

url = "https://khskudtxbypohvnreloi.supabase.co/rest/v1/"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I"

def query(table, params):
    q = urllib.parse.urlencode(params)
    req_url = f"{url}{table}?{q}"
    req = urllib.request.Request(req_url, headers={"apikey": anon_key, "Authorization": f"Bearer {anon_key}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

# trips 11401 and 11402 from google_reservations sql_server_id
# Let's look for trips 11401 and 11402 directly
print("=== Trips 11391-11410 ===")
res = query('trips', {'select': 'id,user_id,client_phone,manual_client_name,status,created_at', 'id': 'gte.11391', 'order': 'id.asc', 'limit': '20'})
print(json.dumps(res, ensure_ascii=False, indent=2))
