const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = 'https://khskudtxbypohvnreloi.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I';

const sb = createClient(supabaseUrl, supabaseKey);

async function diagnose() {
    // 1. Check مؤمن's current profile state
    console.log('=== مؤمن Current Profile ===');
    const { data: profile } = await sb.from('profiles').select('*').eq('id', '1c5aeb93-6601-4f18-9246-8ce42a6e12fd');
    console.log(JSON.stringify(profile, null, 2));

    // 2. Check trips linked to مؤمن's user_id
    console.log('\n=== Trips linked to مؤمن ===');
    const { data: trips } = await sb.from('trips').select('id, user_id, client_phone, manual_client_name, status, pickup_location, dropoff_location, estimated_price, created_at').eq('user_id', '1c5aeb93-6601-4f18-9246-8ce42a6e12fd');
    console.log(JSON.stringify(trips, null, 2));

    // 3. Check what columns trips table actually has (try inserting minimal data)
    console.log('\n=== Testing trips table columns ===');
    // Try to read a trip and see what columns it has
    const { data: sampleTrip } = await sb.from('trips').select('*').limit(1);
    if (sampleTrip && sampleTrip.length > 0) {
        console.log('Available columns in trips:', Object.keys(sampleTrip[0]).join(', '));
    }

    // 4. Check google_reservations for مؤمن
    console.log('\n=== Google Reservations for مؤمن ===');
    const { data: gr } = await sb.from('google_reservations')
        .select('id, sql_server_id, customer_name, customer_phone, trip_date, trip_time, pickup_address, dropoff_address, cost, status')
        .or('customer_phone.ilike.%01070819859%,customer_phone.ilike.%1070819859%');
    for (const r of gr || []) {
        console.log(`GR ${r.id} | sql_id=${r.sql_server_id} | ${r.trip_date} ${r.trip_time} | ${r.pickup_address} -> ${r.dropoff_address} | ${r.cost} EGP | ${r.status}`);
    }
}

diagnose().catch(console.error);
