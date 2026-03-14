import requests
import json
import time

SUPABASE_URL = 'https://wtjwzqvmwnbvjxnmweqq.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NjU0MDMsImV4cCI6MjA4NzA0MTQwM30.kTFK22b18cc1BmvMyLTt-7V113jyf_YrodSB7Km00tY'
SUPABASE_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

FB_PAGE_TOKEN = "EAAPDbwUyvY0BQ3KLTieXWMHZAJZC92eQI9sBwEISipvaaVR9hoteMHWhx0fi8mSXIC4TnTiBHpykmsv6HyAkYK4yQUyQv81ZCF7EZA5CEZAKwPqhfl3jjmaN5muRSk1ZCpNh7OXAQ8Ey7ilMhBmjPvQpLRlzMD8MbYWChOdFxwiFKgPNAqJhg6aVZBR25rvIvChgw1vusjBwHZAeveEMSHpaQ9ps"

def get_facebook_user_name(sender_id):
    if not FB_PAGE_TOKEN:
        return sender_id
        
    url = f"https://graph.facebook.com/v18.0/{sender_id}?fields=first_name,last_name&access_token={FB_PAGE_TOKEN}"
    try:
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
            return name if name else sender_id
    except Exception as e:
        print(e)
    return sender_id

# 1. Fetch all messenger messages
r = requests.get(f"{SUPABASE_URL}/rest/v1/omnichannel_messages?channel=eq.messenger", headers=SUPABASE_HEADERS)
if r.status_code == 200:
    messages = r.json()
    cache = {}
    for msg in messages:
        # Check if the name is the same as the ID (meaning it didn't get resolved before)
        if msg.get('sender_name') == msg.get('sender_id') and not msg.get('is_from_admin'):
            sender_id = msg['sender_id']
            msg_id = msg['id']
            if sender_id not in cache:
                name = get_facebook_user_name(sender_id)
                cache[sender_id] = name
                print(f"Resolved {sender_id} to '{name}'")
            else:
                name = cache[sender_id]
            
            if name != sender_id:
                # Update Supabase
                patch_url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages?id=eq.{msg_id}"
                patch_data = {"sender_name": name}
                pr = requests.patch(patch_url, headers=SUPABASE_HEADERS, json=patch_data)
                if pr.status_code in [200, 204]:
                    print(f"Updated message ID {msg_id}")
                else:
                    print(f"Failed to update ID {msg_id}: {pr.text}")
                time.sleep(0.1)
    print("Done backward sync.")
else:
    print("Failed to fetch messages:", r.text)
