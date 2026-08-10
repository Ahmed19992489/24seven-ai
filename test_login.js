const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = 'https://khskudtxbypohvnreloi.supabase.co';
// Using service role key is needed to check auth.users
// But we only have anon key - let's check via profiles what happens when someone 
// tries to login with 01070819859

const anon_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYzMTIwMjksImV4cCI6MjEwMTg4ODAyOX0.jrK8y5zpDncgFkmdD4hkFRd5-kW1gWdVSRIb0jh7o2I';

const sb = createClient(supabaseUrl, anon_key);

// Simulate what happens when مؤمن tries to log in
// fakeEmail = 01070819859@24seven-client.app
// password = hash of phone

const fakeEmail = '01070819859@24seven-client.app';
// Let's try to compute the password
// From limousine.html, what's the password generation?

async function testLogin() {
    // First, check what profiles exist with this fake email
    console.log('=== Profiles with this email ===');
    const { data: p } = await sb.from('profiles').select('*').eq('phone', '01070819859');
    console.log(JSON.stringify(p, null, 2));

    // Try to sign in and see what happens
    // The phone login creates fakeEmail = phone@24seven-client.app
    // and password = some hash
    // Let's just try signInWithPassword to see if the account exists in auth
    
    // We can't easily simulate the exact password hash from here
    // Let's instead check what the fake email would be and if it's linked
    console.log('\n=== Profile 1c5aeb93 has no email - will phone login create a NEW auth user? ===');
    console.log('Profile email field:', p?.[0]?.email);
    console.log('If profile has NULL email, when user logs in with phone, signInWithPassword will FAIL');
    console.log('Then signUp will CREATE a NEW auth user with a NEW profile ID');
    console.log('The NEW profile will initially say "عميل جوجل" due to the Supabase trigger');
    console.log('');
    console.log('The fix is: the new auth user needs to have the profile linked to the existing مؤمن profile');
}

testLogin().catch(console.error);
