import urllib.request
import urllib.parse
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

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
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Error: {e}")
        return None

# Profiles with phone 01006013164
res = query_supabase("profiles", {"phone": "eq.01006013164"})
print("=== Profiles with phone 01006013164 ===")
if res:
    print(json.dumps(res, indent=2, ensure_ascii=False))
else:
    print("Not found")

# Profiles with email containing nony.harir
res_email = query_supabase("profiles", {"email": "ilike.*nony.harir*"})
print("\n=== Profiles with email containing nony.harir ===")
if res_email:
    print(json.dumps(res_email, indent=2, ensure_ascii=False))
else:
    print("Not found")
