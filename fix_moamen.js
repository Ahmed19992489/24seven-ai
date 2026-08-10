const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = 'https://khskudtxbypohvnreloi.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I';

const sb = createClient(supabaseUrl, supabaseKey);

// مؤمن's profile id
const MOAMEN_USER_ID = '1c5aeb93-6601-4f18-9246-8ce42a6e12fd';
const MOAMEN_PHONE = '01070819859';

async function fix() {
    // 1. Fix مؤمن's profile - set name and role correctly
    console.log('Fixing مؤمن profile...');
    const { error: profileError } = await sb.from('profiles').update({
        full_name: 'مؤمن',
        phone: MOAMEN_PHONE,
        role: 'client'
    }).eq('id', MOAMEN_USER_ID);
    
    if (profileError) {
        console.error('Profile update error:', profileError);
    } else {
        console.log('Profile updated successfully');
    }

    // 2. The trips 11401 and 11402 don't exist yet in trips table
    // We need to create them from google_reservations data
    // Let's check if they have already been created with different IDs
    
    // Look for trips with similar data 
    const { data: existingTrips } = await sb.from('trips')
        .select('id, client_phone, manual_client_name, status, created_at')
        .ilike('client_phone', '%1070819859%');
    
    console.log('\nExisting trips for مؤمن:', existingTrips);

    // 3. Insert the trips from google_reservations that don't exist in trips table
    // gr_id 63593684 -> sql_server_id 11401
    // gr_id 63593685 -> sql_server_id 11402  
    // gr_id 63591239 -> sql_server_id 167 (old system)
    // gr_id 63588794 -> sql_server_id 168 (old system)
    
    const { data: grTrips } = await sb.from('google_reservations')
        .select('*')
        .or('customer_phone.ilike.%01070819859%,customer_phone.ilike.%1070819859%');
    
    console.log('\nGoogle reservations for مؤمن:', grTrips?.length);
    
    for (const gr of grTrips || []) {
        console.log(`GR: ${gr.id} | sql_id: ${gr.sql_server_id} | date: ${gr.trip_date} | pickup: ${gr.pickup_address} | cost: ${gr.cost}`);
    }

    // Insert trips that don't exist
    let insertCount = 0;
    for (const gr of grTrips || []) {
        // Check if a trip with this gr_id already exists
        const { data: existing } = await sb.from('trips')
            .select('id')
            .eq('google_reservation_id', gr.id);
        
        // If not found, let's check another way
        if (!existing || existing.length === 0) {
            // Insert the trip
            const tripData = {
                user_id: MOAMEN_USER_ID,
                pickup_location: gr.pickup_address || '',
                dropoff_location: gr.dropoff_address || '',
                estimated_price: gr.cost || 0,
                final_price: gr.cost || 0,
                car_type: gr.car_type?.toLowerCase() || 'van',
                status: 'completed',
                payment_status: 'unpaid',
                manual_client_name: gr.customer_name || 'مؤمن',
                client_phone: MOAMEN_PHONE,
                admin_notes: `حجز من الشيت 📝\nالعميل: ${gr.customer_name}\nرقم: ${gr.customer_phone}\nنوع التحصيل: ${gr.payment_method || 'cash'}`,
                details: {
                    date: gr.trip_date,
                    time: gr.trip_time,
                    car: gr.car_type,
                    pax: gr.passengers || 1,
                    bags: gr.bags || 0
                }
            };
            
            const { data: newTrip, error: insertError } = await sb.from('trips').insert([tripData]).select();
            if (insertError) {
                console.log(`Error inserting trip for gr ${gr.id}:`, insertError.message);
            } else {
                console.log(`Inserted trip ${newTrip?.[0]?.id} for gr ${gr.id}`);
                insertCount++;
            }
        }
    }
    
    console.log(`\nInserted ${insertCount} trips for مؤمن`);
}

fix().catch(console.error);
