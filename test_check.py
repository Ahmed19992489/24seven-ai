import urllib.request
import urllib.parse
import json

url = "https://khskudtxbypohvnreloi.supabase.co/rest/v1/"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I"

def query_supabase(table, params_dict):
    query_str = urllib.parse.urlencode(params_dict)
    req_url = f"{url}{table}?{query_str}"
    req = urllib.request.Request(
        req_url,
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())

res = query_supabase('trips', {'manual_client_name': 'eq.مؤمن'})
for r in res:
    print(f"ID: {r.get('id')}, user_id: {r.get('user_id')}, phone: {r.get('client_phone')}")
