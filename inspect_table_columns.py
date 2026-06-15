import json

with open('supabase_spec.json', 'r', encoding='utf-8') as f:
    spec = json.load(f)

definitions = spec.get('definitions', {})
omni_table = definitions.get('omnichannel_messages', {})

print("omnichannel_messages properties:")
properties = omni_table.get('properties', {})
for prop, details in properties.items():
    print(f"  {prop}: {details.get('type')} - {details.get('description', '')}")
