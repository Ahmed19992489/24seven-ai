import requests
import json

SUPABASE_URL = 'https://khskudtxbypohvnreloi.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjMxMjAyOSwiZXhwIjoyMTAxODg4MDI5fQ.uyCTVGkoeoz4xB3r2muV_fLiI62QIw-65g2nVeIb62w'

H = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}'
}

r = requests.get(f"{SUPABASE_URL}/rest/v1/", headers=H)
if r.status_code == 200:
    spec = r.json()
    # Write to a file
    with open('supabase_spec.json', 'w', encoding='utf-8') as f:
        json.dump(spec, f, indent=2)
    print("Successfully retrieved OpenAPI spec")
    # Print paths keys to see RPCs
    paths = spec.get('paths', {})
    rpcs = [k for k in paths.keys() if k.startswith('/rpc/')]
    print("Exposed RPCs:")
    for rpc in rpcs:
        print(rpc)
else:
    print(f"Error: {r.status_code} - {r.text}")
