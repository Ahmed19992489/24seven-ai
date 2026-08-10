const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = 'https://khskudtxbypohvnreloi.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I';

const sb = createClient(supabaseUrl, supabaseKey);

const MOAMEN_USER_ID = '1c5aeb93-6601-4f18-9246-8ce42a6e12fd';
const MOAMEN_PHONE = '01070819859';

async function fix() {
    // 1. Fix profile
    console.log('Fixing مؤمن profile...');
    const { error: profileError } = await sb.from('profiles').update({
        full_name: 'مؤمن',
        phone: MOAMEN_PHONE,
        role: 'client'
    }).eq('id', MOAMEN_USER_ID);
    
    if (profileError) {
        console.error('Profile update error:', profileError.message);
    } else {
        console.log('✅ Profile updated to role=client, full_name=مؤمن');
    }

    // 2. Get مؤمن's google_reservations that are linked to trips table
    // sql_server_id 11401 and 11402 mean those trips should have been inserted to trips table
    // But they haven't. We need to find their trips via the gr_id method
    
    // Look for trips that were created from these google_reservations records
    const { data: grTrips } = await sb.from('google_reservations')
        .select('*')
        .or('customer_phone.ilike.%01070819859%,customer_phone.ilike.%1070819859%');
    
    console.log(`\nFound ${grTrips?.length} google_reservation records for مؤمن`);
    
    // 3. Check which ones have been pushed to trips table
    for (const gr of grTrips || []) {
        const sqlId = gr.sql_server_id;
        
        if (sqlId && !isNaN(parseInt(sqlId))) {
            const tripId = parseInt(sqlId);
            // Check if trip exists
            const { data: existTrip } = await sb.from('trips')
                .select('id, user_id, status')
                .eq('id', tripId);
            
            if (existTrip && existTrip.length > 0) {
                const trip = existTrip[0];
                console.log(`GR ${gr.id} -> Trip ${tripId} EXISTS | user_id: ${trip.user_id} | status: ${trip.status}`);
                
                // Link to مؤمن if not already linked
                if (!trip.user_id) {
                    const { error } = await sb.from('trips').update({
                        user_id: MOAMEN_USER_ID,
                        client_phone: MOAMEN_PHONE,
                        manual_client_name: 'مؤمن'
                    }).eq('id', tripId);
                    console.log(`  -> Linked trip ${tripId} to مؤمن: ${error ? error.message : '✅'}`);
                }
            } else {
                console.log(`GR ${gr.id} -> Trip ${tripId} NOT FOUND in trips table`);
                
                // Insert a new trip for this reservation
                const carType = (gr.car_type || 'Van').toLowerCase();
                const normalizedCarType = carType === 'van' ? 'van' : carType === 'suv' ? 'suv' : 'sedan';
                
                const newTrip = {
                    user_id: MOAMEN_USER_ID,
                    pickup_location: gr.pickup_address || '',
                    dropoff_location: gr.dropoff_address || '',
                    estimated_price: gr.cost || 0,
                    final_price: gr.cost || 0,
                    car_type: normalizedCarType,
                    status: 'approved',
                    payment_status: 'unpaid',
                    manual_client_name: gr.customer_name?.trim() || 'مؤمن',
                    client_phone: MOAMEN_PHONE,
                    trip_date: gr.trip_date,
                    trip_time: gr.trip_time,
                    admin_notes: `حجز من الشيت 📝\nالعميل: ${gr.customer_name?.trim()}\nرقم: ${gr.customer_phone}\nسيارة: ${gr.car_type} | رحلة: ${gr.trip_type || 'one_way'}\nركاب: ${gr.passengers || 1} | شنط: ${gr.bags || 0}\nالتاريخ: ${gr.trip_date} | الوقت: ${gr.trip_time}\nنوع التحصيل: ${gr.payment_method || 'cash'}\nملاحظات: ${gr.notes || ''}`,
                };
                
                const { data: inserted, error: insertErr } = await sb.from('trips').insert([newTrip]).select();
                if (insertErr) {
                    console.log(`  Error inserting: ${insertErr.message}`);
                } else {
                    console.log(`  ✅ Inserted new trip ID ${inserted?.[0]?.id}`);
                }
            }
        } else {
            console.log(`GR ${gr.id} has no valid sql_server_id (${sqlId})`);
        }
    }

    // 4. Also check if the moderator trips (167, 168) need to be linked
    // These were old trips - let's check them
    console.log('\nChecking old trips 167 and 168...');
    for (const oldId of [167, 168]) {
        const { data: oldTrip } = await sb.from('trips').select('id, user_id, status, client_phone, manual_client_name').eq('id', oldId);
        if (oldTrip && oldTrip.length > 0) {
            console.log(`Trip ${oldId}: user_id=${oldTrip[0].user_id}, phone=${oldTrip[0].client_phone}, name=${oldTrip[0].manual_client_name}`);
        } else {
            console.log(`Trip ${oldId}: NOT FOUND`);
        }
    }
}

fix().catch(console.error);
