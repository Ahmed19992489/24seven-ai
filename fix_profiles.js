const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = 'https://khskudtxbypohvnreloi.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I';

const sb = createClient(supabaseUrl, supabaseKey);

async function fixProfiles() {
    const { data: profiles, error } = await sb.from('profiles').select('*').eq('full_name', 'عميل جوجل').eq('role', 'moderator');
    
    if (error) {
        console.error(error);
        return;
    }

    let fixedCount = 0;
    for (const p of profiles) {
        if (p.email && p.email.endsWith('@24seven-client.app')) {
            const phone = p.email.split('@')[0];
            const cleanedPhone = phone.replace(/^0+/, '');
            let realName = 'عميل ' + phone.slice(-4);
            
            const { data: reservations } = await sb.from('google_reservations')
                .select('customer_name')
                .or(`customer_phone.ilike.%${cleanedPhone}%,customer_phone.ilike.%${phone}%`)
                .order('created_at', { ascending: false })
                .limit(1);
                
            if (reservations && reservations.length > 0 && reservations[0].customer_name) {
                realName = reservations[0].customer_name;
            }
            
            console.log(`Fixing ${phone} -> ${realName}`);
            await sb.from('profiles').update({
                full_name: realName,
                phone: phone,
                role: 'client'
            }).eq('id', p.id);
            fixedCount++;
        }
    }
    console.log(`Fixed ${fixedCount} profiles.`);
}

fixProfiles();
