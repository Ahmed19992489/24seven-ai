import os
import sys
import time
import requests
import json
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN") or "EAAPDbwUyvY0BRN0VW4bIHPLRpeA7qHqK5TyFpNxJ8fuFcvVCshuBwZC52F59Q6oNH671nLZBbAiEsGSB55Vq0sHjyMIB4QNStzt6sFxRL7ImzttrnuFkHVTYWGZC0J2MgbBGfqo3dOi7Wo5QagQ7pY3vhZAztfKZBhNZCxGrVeGRIqz7pUkHHC2iM4ZA0mDje9oEXZCm"
PAGE_ID = "101903822442322"
API_DB_URL = "https://24seven-ai.com/api/db"

def sync_facebook_messages():
    if not FB_PAGE_TOKEN:
        print("❌ No FB_PAGE_TOKEN configured.")
        return

    url = "https://graph.facebook.com/v19.0/me/conversations"
    params = {
        "access_token": FB_PAGE_TOKEN,
        "fields": "id,updated_time,participants,messages.limit(15){id,message,from,created_time,attachments}",
        "limit": 25
    }

    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code != 200:
            print(f"❌ Error fetching conversations from Meta: {r.status_code} - {r.text[:200]}")
            return

        data = r.json().get("data", [])

        # Fetch recent messages from Neon via /api/db to prevent duplicates
        existing_set = set()
        try:
            chk_res = requests.post(API_DB_URL, json={
                "action": "select",
                "table": "omnichannel_messages",
                "select": "sender_id,message_text,is_from_admin",
                "limit": 200
            }, timeout=8)
            if chk_res.status_code == 200:
                rows = chk_res.json().get("data", [])
                for row in rows:
                    existing_set.add((str(row.get('sender_id')), str(row.get('message_text')), bool(row.get('is_from_admin'))))
        except Exception as e:
            print(f"Warning: Could not check duplicates: {e}")

        total_inserted = 0
        for conv in data:
            participants = conv.get("participants", {}).get("data", [])
            client_p = None
            for p in participants:
                if str(p.get("id")) != str(PAGE_ID):
                    client_p = p
                    break

            if not client_p:
                continue

            client_id = str(client_p.get("id"))
            client_name = client_p.get("name") or "عميل فيسبوك ماسنجر"

            messages = conv.get("messages", {}).get("data", [])
            messages.reverse()

            for msg in messages:
                msg_text = msg.get("message", "")
                from_obj = msg.get("from", {})
                from_id = str(from_obj.get("id"))
                is_admin = (from_id == str(PAGE_ID))

                attachments = msg.get("attachments", {}).get("data", [])
                if not msg_text and attachments:
                    att = attachments[0]
                    att_type = att.get("type", "image")
                    image_data = att.get("image_data", {})
                    att_url = image_data.get("url") or att.get("file_url")
                    msg_text = f"MEDIA_{att_type.upper()}:{att_url}" if att_url else f"📎 [{att_type}]"

                if not msg_text:
                    continue

                if (client_id, msg_text, is_admin) in existing_set:
                    continue

                created_time = msg.get("created_time")
                db_data = {
                    "channel": "messenger",
                    "sender_id": client_id,
                    "sender_name": client_name if not is_admin else "فريق 24Seven",
                    "message_text": msg_text,
                    "is_from_admin": is_admin,
                    "read_by_admin": is_admin,
                    "created_at": created_time or datetime.utcnow().isoformat()
                }

                try:
                    res = requests.post(API_DB_URL, json={
                        "action": "insert",
                        "table": "omnichannel_messages",
                        "data": db_data
                    }, timeout=6)
                    if res.status_code == 200 and res.json().get("status") == "ok":
                        total_inserted += 1
                        existing_set.add((client_id, msg_text, is_admin))
                except Exception as ex:
                    print(f"Insert error: {ex}")

        if total_inserted > 0:
            print(f"✅ Sync complete! Inserted {total_inserted} new Meta messages with verified customer names.")
        else:
            print("✨ Meta sync check complete - all messages are up to date.")

    except Exception as e:
        print(f"❌ Exception in sync_facebook_messages: {e}")

if __name__ == "__main__":
    is_loop = "--loop" in sys.argv
    if is_loop:
        print("🔄 Meta Continuous Sync Daemon active (polling every 30s)...")
        while True:
            try:
                sync_facebook_messages()
            except Exception as e:
                print(f"Loop error: {e}")
            time.sleep(30)
    else:
        sync_facebook_messages()
