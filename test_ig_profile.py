import requests
import json

INSTAGRAM_TOKEN = "IGAAMRP14aPG1BZAFlpX3dwczlsdTdFMnlISk5keldkclZAPS3pMR1pzYXJMc2FXcjJuRnNpTnRMdWsxS2ZACS3JjQVdiUzRFWXBHUl92eDg5V1d5QmJGUnhDdHVPcFJoNnRsTG16UWxFd05sY2dkcTlaUGNuNFdsa2pyalc5UUI1cwZDZD"
sender_id = "1414133264069790"

url = f"https://graph.facebook.com/v17.0/{sender_id}"
params = {"fields": "username,name", "access_token": INSTAGRAM_TOKEN}

try:
    r = requests.get(url, params=params)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
except Exception as e:
    print(f"Error: {e}")
