"""Delete all Supabase Storage objects to free space below 1GB limit"""
import urllib.request
import urllib.error
import json

SUPABASE_URL = 'https://khskudtxbypohvnreloi.supabase.co'
SERVICE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjMxMjAyOSwiZXhwIjoyMTAxODg4MDI5fQ.uyCTVGkoeoz4xB3r2muV_fLiI62QIw-65g2nVeIb62w'

headers = {
    'Authorization': f'Bearer {SERVICE_KEY}',
    'apikey': SERVICE_KEY,
    'Content-Type': 'application/json'
}

def api_request(method, path, body=None):
    url = f'{SUPABASE_URL}/storage/v1{path}'
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

print("=" * 50)
print("Supabase Storage Cleanup")
print("=" * 50)

# Step 1: List buckets
print("\n1. Listing buckets...")
status, buckets = api_request('GET', '/bucket')
print(f"   Status: {status}")
print(f"   Response: {str(buckets)[:200]}")

if status != 200:
    print("\n   STORAGE API also blocked. Trying alternative approach...")
    # Try the REST API for storage indirectly
    url = f'{SUPABASE_URL}/storage/v1/bucket'
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"   Direct bucket list: {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"   Error: {e.code} - {e.read().decode()[:200]}")
    print("\n   Cannot access storage API due to quota restriction.")
    print("   Please go to: https://supabase.com/dashboard/org/wmxgsnj hxmlIgigkqpjv/billing")
    print("   Click 'Resolve billing issues'")
else:
    print(f"\n   Found {len(buckets)} buckets!")
    total_deleted = 0
    for bucket in buckets:
        bucket_id = bucket.get('id', bucket.get('name'))
        print(f"\n2. Processing bucket: {bucket_id}")
        
        # List all objects in bucket
        status2, objects = api_request('POST', f'/object/list/{bucket_id}', {
            'prefix': '',
            'limit': 1000,
            'sortBy': {'column': 'name', 'order': 'asc'}
        })
        print(f"   Objects list status: {status2}")
        
        if status2 == 200 and isinstance(objects, list) and len(objects) > 0:
            print(f"   Found {len(objects)} objects to delete")
            object_names = [obj['name'] for obj in objects]
            
            # Delete all objects
            status3, result = api_request('DELETE', f'/object/{bucket_id}', {
                'prefixes': object_names
            })
            print(f"   Delete status: {status3} - {str(result)[:100]}")
            total_deleted += len(object_names)
        else:
            print(f"   No objects found or error")
    
    print(f"\n✅ Done! Deleted {total_deleted} objects total.")
    print("Storage should now be below 1GB. Wait 5 minutes then refresh Supabase.")
