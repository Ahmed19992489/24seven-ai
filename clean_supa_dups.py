import urllib.request
import urllib.parse
import json

url = "https://khskudtxbypohvnreloi.supabase.co/rest/v1/"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I"

def query_supabase(table, params_dict=None):
    if params_dict is None:
        params_dict = {}
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

def delete_supabase(table, params_dict):
    query_str = urllib.parse.urlencode(params_dict)
    req_url = f"{url}{table}?{query_str}"
    req = urllib.request.Request(
        req_url,
        method="DELETE",
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req) as response:
        pass

print("Fetching google_reservations...")
res = query_supabase('google_reservations', {'select': 'id,customer_phone,trip_date,trip_time,pickup_address,dropoff_address,created_at'})
print(f"Total reservations: {len(res)}")

seen = {}
to_delete = []

# Sort by created_at ascending, so we keep the oldest
res.sort(key=lambda x: x.get('created_at', ''))

for r in res:
    key = (
        r.get('customer_phone'),
        r.get('trip_date'),
        r.get('trip_time'),
        r.get('pickup_address'),
        r.get('dropoff_address')
    )
    if key in seen:
        to_delete.append(r['id'])
    else:
        seen[key] = r['id']

print(f"Found {len(to_delete)} duplicates.")
if to_delete:
    for i in range(0, len(to_delete), 50):
        batch = to_delete[i:i+50]
        delete_supabase('google_reservations', {'id': f"in.({','.join(map(str, batch))})"})
    print("Deleted duplicates from Supabase google_reservations.")
else:
    print("No duplicates found.")
