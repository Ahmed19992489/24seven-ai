import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://khskudtxbypohvnreloi.supabase.co/rest/v1/"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I"
vendor_id = "344be688-a74a-4ed5-ae88-d7d0288c0a1b"

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
        print(f"Error querying {table}: {e}")
        return None

txs = query_supabase("vendor_transactions", f"vendor_id=eq.{vendor_id}")
if txs:
    print(f"Found {len(txs)} transactions for vendor {vendor_id}:")
    for t in txs:
        print(f"ID: {t.get('id')}, Amount: {t.get('amount')}, Type: {t.get('type')}, Trip ID: {t.get('trip_id')}, Created At: {t.get('created_at')}")
else:
    print(f"No transactions found for vendor {vendor_id}")
