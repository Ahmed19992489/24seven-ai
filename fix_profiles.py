from supabase import create_client, Client
import os
import re

url = "https://khskudtxbypohvnreloi.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I"
supabase: Client = create_client(url, key)

res = supabase.table('profiles').select('*').eq('full_name', 'عميل جوجل').eq('role', 'moderator').execute()

fixed_count = 0
for p in res.data:
    if p.get('email') and p['email'].endswith('@24seven-client.app'):
        phone = p['email'].split('@')[0]
        
        # find name
        cleaned_phone = phone.lstrip('0')
        real_name = 'عميل ' + phone[-4:]
        
        # fetch reservations
        r_res = supabase.table('google_reservations').select('customer_name').or_(
            f"customer_phone.ilike.%{cleaned_phone}%,customer_phone.ilike.%{phone}%"
        ).order('created_at', desc=True).limit(1).execute()
        
        if r_res.data and r_res.data[0].get('customer_name'):
            real_name = r_res.data[0]['customer_name']
            
        print(f"Fixing {phone} -> {real_name}")
        supabase.table('profiles').update({
            'full_name': real_name,
            'phone': phone,
            'role': 'client'
        }).eq('id', p['id']).execute()
        fixed_count += 1

print(f"Fixed {fixed_count} profiles.")
