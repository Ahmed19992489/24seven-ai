// انسخ هذا الكود في Console المتصفح
(async () => {
    console.log('=== DEBUG START ===');
    console.log('1. apiFetch type:', typeof apiFetch);
    console.log('2. getStaffApiBaseUrl():', getStaffApiBaseUrl());
    
    const apiBase = getStaffApiBaseUrl();
    console.log('3. Testing fetch to:', apiBase + '/api/whatsapp/instances');
    
    try {
        const res = await apiFetch(`${apiBase}/api/whatsapp/instances`);
        console.log('4. Response status:', res.status);
        const data = await res.json();
        console.log('5. Data:', JSON.stringify(data).substring(0, 200));
    } catch(e) {
        console.error('6. ERROR:', e.message);
    }
    
    const el = document.getElementById('page-whatsapp-settings');
    console.log('7. page-whatsapp-settings hidden?', el ? el.classList.contains('hidden') : 'ELEMENT NOT FOUND');
    console.log('8. whatsapp-instances-list innerHTML:', document.getElementById('whatsapp-instances-list')?.innerHTML?.substring(0, 100));
    console.log('=== DEBUG END ===');
})();
