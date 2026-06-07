import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://wtjwzqvmwnbvjxnmweqq.supabase.co/rest/v1/"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NjU0MDMsImV4cCI6MjA4NzA0MTQwM30.kTFK22b18cc1BmvMyLTt-7V113jyf_YrodSB7Km00tY"
vendor_id = "344be688-a74a-4ed5-ae88-d7d0288c0a1b"

def delete_supabase(table, filter_str):
    req_url = f"{url}{table}?{filter_str}"
    req = urllib.request.Request(
        req_url,
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}"
        },
        method="DELETE"
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode()
    except Exception as e:
        print(f"Error deleting from {table}: {e}")
        return None

print("Deleting all transactions for vendor 344be688-a74a-4ed5-ae88-d7d0288c0a1b...")
res = delete_supabase("vendor_transactions", f"vendor_id=eq.{vendor_id}")
print("Done. Response:", res)
