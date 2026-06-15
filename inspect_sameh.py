import urllib.request
import urllib.parse
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://wtjwzqvmwnbvjxnmweqq.supabase.co/rest/v1/"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NjU0MDMsImV4cCI6MjA4NzA0MTQwM30.kTFK22b18cc1BmvMyLTt-7V113jyf_YrodSB7Km00tY"

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

# Search google_reservations for customer_name containing 'سامح عاطف'
res = query_supabase("google_reservations", {
    "customer_name": "ilike.*سامح عاطف*",
    "order": "created_at.desc",
    "limit": "10"
})
print("=== Google Reservations for سامح عاطف ===")
if res:
    for r in res:
        print(f"id: {r.get('id')}, customer_name: {r.get('customer_name')}, customer_phone: {r.get('customer_phone')}, trip_date: {r.get('trip_date')}, trip_time: {r.get('trip_time')}, sheet_row: {r.get('sheet_row')}, sql_server_id: {r.get('sql_server_id')}")
else:
    print("No google_reservations found")

# Search trips for client_phone or manual_client_name containing 'سامح عاطف'
trips = query_supabase("trips", {
    "manual_client_name": "ilike.*سامح عاطف*",
    "order": "created_at.desc",
    "limit": "10"
})
print("\n=== Trips for سامح عاطف ===")
if trips:
    for t in trips:
        print(f"id: {t.get('id')}, name: {t.get('manual_client_name')}, phone: {t.get('client_phone')}, trip_date: {t.get('trip_date')}, estimated_price: {t.get('estimated_price')}")
else:
    print("No trips found")
