import requests
import json

SUPABASE_URL = 'https://wtjwzqvmwnbvjxnmweqq.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTQ2NTQwMywiZXhwIjoyMDg3MDQxNDAzfQ.WYNflQntWBCHXDnxFf2C1X1IerYZtMfMT6p6P4Dx0Vg'

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
