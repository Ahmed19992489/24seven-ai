const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = 'https://khskudtxbypohvnreloi.supabase.co';
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I';

const sb = createClient(supabaseUrl, supabaseKey);

async function testUpsert() {
    const { data, error } = await sb.from('profiles').upsert({
        id: '1c5aeb93-6601-4f18-9246-8ce42a6e12fd',
        phone: '01070819859',
        full_name: 'مؤمن',
        wallet_balance: 0
    });
    console.log("Data:", data);
    console.log("Error:", error);
}

testUpsert();
