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

FB_PAGE_TOKEN = "EAAPDbwUyvY0BRN0VW4bIHPLRpeA7qHqK5TyFpNxJ8fuFcvVCshuBwZC52F59Q6oNH671nLZBbAiEsGSB55Vq0sHjyMIB4QNStzt6sFxRL7ImzttrnuFkHVTYWGZC0J2MgbBGfqo3dOi7Wo5QagQ7pY3vhZAztfKZBhNZCxGrVeGRIqz7pUkHHC2iM4ZA0mDje9oEXZCm"

def get_facebook_user_name(sender_id):
    if not FB_PAGE_TOKEN:
        return sender_id

    # محاولة 1: عبر محادثات الصفحة (تجنب مشاكل الصلاحيات في الـ Dev Mode)
    try:
        url = "https://graph.facebook.com/v18.0/me/conversations"
        params = {
            "access_token": FB_PAGE_TOKEN,
            "user_id": sender_id,
            "fields": "participants"
        }
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            for conv in data.get('data', []):
                for p in conv.get('participants', {}).get('data', []):
                    if str(p.get('id')) == str(sender_id):
                        name = p.get('name', '').strip()
                        if name:
                            return name
    except Exception as e:
        print(f"Error in conversations lookup: {e}")

    # محاولة 2: عبر Graph API المباشر للملف الشخصي (fallback)
    url = f"https://graph.facebook.com/v18.0/{sender_id}?fields=first_name,last_name&access_token={FB_PAGE_TOKEN}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
            if name:
                return name
    except Exception as e:
        print(f"Error in profile lookup: {e}")

    return sender_id

# 1. Fetch all messenger messages
r = requests.get(f"{SUPABASE_URL}/rest/v1/omnichannel_messages?channel=eq.messenger", headers=SUPABASE_HEADERS)
if r.status_code == 200:
    messages = r.json()
    cache = {}
    for msg in messages:
        # Check if the name is 'Messenger User' or matches the sender_id (meaning it didn't get resolved before)
        sender_id = msg['sender_id']
        sender_name = msg.get('sender_name')
        msg_id = msg['id']
        
        if (sender_name == 'Messenger User' or sender_name == sender_id) and not msg.get('is_from_admin'):
            if sender_id not in cache:
                name = get_facebook_user_name(sender_id)
                cache[sender_id] = name
                print(f"Resolved {sender_id} to '{name}'")
            else:
                name = cache[sender_id]
            
            if name != sender_id and name != 'Messenger User':
                # Update Supabase
                patch_url = f"{SUPABASE_URL}/rest/v1/omnichannel_messages?id=eq.{msg_id}"
                patch_data = {"sender_name": name}
                pr = requests.patch(patch_url, headers=SUPABASE_HEADERS, json=patch_data)
                if pr.status_code in [200, 204]:
                    print(f"Updated message ID {msg_id} to name '{name}'")
                else:
                    print(f"Failed to update ID {msg_id}: {pr.text}")
                time.sleep(0.1)
    print("Done backward sync.")
else:
    print("Failed to fetch messages:", r.text)
