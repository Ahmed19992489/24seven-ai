import sys, json, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding='utf-8')

url = "https://khskudtxbypohvnreloi.supabase.co/rest/v1/"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I"

def query(table, params):
    q = urllib.parse.urlencode(params)
    req_url = f"{url}{table}?{q}"
    req = urllib.request.Request(req_url, headers={"apikey": anon_key, "Authorization": f"Bearer {anon_key}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

# The google_reservations has sql_server_id 11401 and 11402
# This means trips table should have id=11401, 11402
# But the highest trip ID is 11392 - so 11401 and 11402 don't exist yet in trips table!
# They are in google_reservations but waiting to be pushed to trips table

print("=== Max trip ID ===")
res = query('trips', {'select': 'id', 'order': 'id.desc', 'limit': '5'})
for t in res:
    print(f"id:{t['id']}")

print("\n=== Checking google_reservations for مؤمن - sql_server_id details ===")
res2 = query('google_reservations', {'select': 'id,sql_server_id,customer_name,customer_phone,status,trip_date', 'customer_phone': 'ilike.%1070819859%', 'order': 'created_at.desc'})
for r in res2:
    print(f"gr_id:{r['id']} | sql_id:{r['sql_server_id']} | name:{r['customer_name']} | phone:{r['customer_phone']} | status:{r['status']} | date:{r['trip_date']}")
