import urllib.request
import urllib.parse
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://khskudtxbypohvnreloi.supabase.co/rest/v1/"
service_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjMxMjAyOSwiZXhwIjoyMTAxODg4MDI5fQ.uyCTVGkoeoz4xB3r2muV_fLiI62QIw-65g2nVeIb62w"

def query_supabase(table, params_dict):
    query_str = urllib.parse.urlencode(params_dict)
    req_url = f"{url}{table}?{query_str}"
    req = urllib.request.Request(
        req_url,
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Error: {e}")
        return None

res = query_supabase("whatsapp_instances", {
    "order": "created_at.desc"
})
print("=== WhatsApp Instances ===")
if res:
    for r in res:
        print(f"ID: {r.get('id')}, Name: {r.get('instance_name')}, Provider: {r.get('provider')}, Status: {r.get('status')}, Phone: {r.get('phone')}")
else:
    print("No instances found")
