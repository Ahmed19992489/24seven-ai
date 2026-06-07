import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://wtjwzqvmwnbvjxnmweqq.supabase.co/rest/v1/"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NjU0MDMsImV4cCI6MjA4NzA0MTQwM30.kTFK22b18cc1BmvMyLTt-7V113jyf_YrodSB7Km00tY"

def query_supabase(table, params=""):
    req_url = f"{url}{table}?{params}"
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

# Fetch google_reservations where client_decision is not empty
res = query_supabase("google_reservations", "select=id,customer_name,client_decision,sheet_row,sql_server_id,updated_at&order=updated_at.desc&limit=10")
if res:
    print("Latest 10 modified reservations:")
    for r in res:
        print(f"ID: {r.get('id')}, Name: {r.get('customer_name')}, Decision: {r.get('client_decision')}, Row: {r.get('sheet_row')}, SQL ID: {r.get('sql_server_id')}, Updated At: {r.get('updated_at')}")
else:
    print("No data or empty table")
