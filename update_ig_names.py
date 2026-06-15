import requests
import json

SUPABASE_URL = 'https://wtjwzqvmwnbvjxnmweqq.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NjU0MDMsImV4cCI6MjA4NzA0MTQwM30.kTFK22b18cc1BmvMyLTt-7V113jyf_YrodSB7Km00tY'
FB_PAGE_TOKEN = "EAAPDbwUyvY0BRN0VW4bIHPLRpeA7qHqK5TyFpNxJ8fuFcvVCshuBwZC52F59Q6oNH671nLZBbAiEsGSB55Vq0sHjyMIB4QNStzt6sFxRL7ImzttrnuFkHVTYWGZC0J2MgbBGfqo3dOi7Wo5QagQ7pY3vhZAztfKZBhNZCxGrVeGRIqz7pUkHHC2iM4ZA0mDje9oEXZCm"

H = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
}

# 1. Fetch all unique sender_ids for instagram channel where sender_name is 'Instagram User' or id-like
url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages?channel=eq.instagram&select=sender_id,sender_name"
r = requests.get(url, headers=H)
if r.status_code == 200:
    messages = r.json()
    unique_senders = set()
    for m in messages:
        sid = m.get('sender_id')
        sname = m.get('sender_name')
        if sid and (sname == 'Instagram User' or sname == sid):
            unique_senders.add(sid)
    
    print(f"Found {len(unique_senders)} senders needing name update: {unique_senders}")
    
    for sid in unique_senders:
        # Query Meta Graph API using FB_PAGE_TOKEN
        profile_url = f"https://graph.facebook.com/v17.0/{sid}"
        params = {"fields": "username,name", "access_token": FB_PAGE_TOKEN}
        try:
            profile_res = requests.get(profile_url, params=params)
            if profile_res.status_code == 200:
                profile_data = profile_res.json()
                real_name = profile_data.get("username") or profile_data.get("name")
                if real_name:
                    print(f"Resolved {sid} to '{real_name}'")
                    # Update all omnichannel_messages in Supabase for this sender_id
                    update_url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages?sender_id=eq.{sid}"
                    up_res = requests.patch(update_url, headers=H, json={"sender_name": real_name})
                    print(f"Updated Supabase status: {up_res.status_code}")
                else:
                    print(f"Could not find username in profile data for {sid}")
            else:
                print(f"Failed to fetch profile for {sid}: {profile_res.status_code} - {profile_res.text}")
        except Exception as e:
            print(f"Error updating {sid}: {e}")
else:
    print(f"Error fetching messages: {r.status_code} - {r.text}")
