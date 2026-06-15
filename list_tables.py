import json

with open('supabase_spec.json', 'r', encoding='utf-8') as f:
    spec = json.load(f)

print("Tables/Views in OpenAPI spec:")
paths = spec.get('paths', {})
tables = []
for p in paths.keys():
    if not p.startswith('/rpc/') and p != '/':
        tables.append(p.lstrip('/'))

print(sorted(tables))
