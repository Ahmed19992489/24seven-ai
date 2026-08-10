import requests
import json

SUPABASE_URL = 'https://khskudtxbypohvnreloi.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I'

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
