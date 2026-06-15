import requests
import json

SUPABASE_URL = 'https://wtjwzqvmwnbvjxnmweqq.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NjU0MDMsImV4cCI6MjA4NzA0MTQwM30.kTFK22b18cc1BmvMyLTt-7V113jyf_YrodSB7Km00tY'

H = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}'
}

# Fetch the messages for the sender
url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages?sender_id=eq.1414133264069790&select=*"
r = requests.get(url, headers=H)
if r.status_code == 200:
    with open('query_ig_result.json', 'w', encoding='utf-8') as f:
        json.dump(r.json(), f, indent=2, ensure_ascii=False)
    print("Success: results written to query_ig_result.json")
else:
    print(f"Error: {r.status_code} - {r.text}")
