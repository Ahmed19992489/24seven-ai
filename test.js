
        const supabaseUrl = 'https://wtjwzqvmwnbvjxnmweqq.supabase.co';
        const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0NjU0MDMsImV4cCI6MjA4NzA0MTQwM30.kTFK22b18cc1BmvMyLTt-7V113jyf_YrodSB7Km00tY';
        const sbClient = supabase.createClient(supabaseUrl, supabaseKey);

        showPage('dashboard');
        
        // Setup real-time listeners globally
        setupSupportRealtime();

        function toggleSidebar() {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebar-overlay');
            if (sidebar.classList.contains('active')) {
                sidebar.classList.remove('active'); overlay.classList.remove('active');
            } else {
                sidebar.classList.add('active'); overlay.classList.add('active');
            }
        }

        function showPage(pageId) {
            document.querySelectorAll('.page-section').forEach(e => e.classList.add('hidden'));
            document.getElementById(`page-${pageId}`).classList.remove('hidden');
            document.querySelectorAll('.sidebar-item').forEach(e => e.classList.remove('active'));
            document.getElementById(`nav-${pageId}`).classList.add('active');
            if (window.innerWidth <= 768) { document.getElementById('sidebar').classList.remove('active'); document.getElementById('sidebar-overlay').classList.remove('active'); }
            if (pageId === 'dashboard') loadDashboard();
            if (pageId === 'operations') { loadOperations(); setupOpsRealtime(); }
            if (pageId === 'crm') loadCRM();
            if (pageId === 'finance') loadFinance();
            if (pageId === 'fleet') loadFleetList();
            if (pageId === 'pricing') loadPricing();
            if (pageId === 'chat') loadAdminChats();
            if (pageId === 'ratings') loadRatings();
            if (pageId === 'coupons') loadCouponsPage();
            if (pageId === 'staff') loadStaff();
            if (pageId === 'ai-assistant') {
                 // No specific load needed, but good to scroll to bottom
                 setTimeout(() => {
                    const box = document.getElementById('ai-chat-messages');
                    if(box) box.scrollTop = box.scrollHeight;
                 }, 100);
            }
        }

        async function loadDashboard() {
            const { count } = await sbClient.from('trips').select('*', { count: 'exact', head: true });
            document.getElementById('kpi-total').innerText = count || 0;
            const { data: vaults } = await sbClient.from('vaults').select('*');
            if (vaults) {
                const main = vaults.find(v => v.name === 'الخزينة الرئيسية') || { balance: 0 };
                const maint = vaults.find(v => v.name === 'خزنة الصيانة') || { balance: 0 };
                const cars = vaults.find(v => v.name === 'خزنة رواتب السيارات') || { balance: 0 };
                document.getElementById('kpi-main-vault').innerText = `${main.balance} EGP`;
                document.getElementById('kpi-maint-vault').innerText = `${maint.balance} EGP`;
                document.getElementById('kpi-cars-salary').innerText = `${cars.balance} EGP`;
            }

            // تحميل أداء الموظفين
            loadStaffStats();
        }

        async function loadStaffStats() {
            try {
                const monthStart = new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().split('T')[0];
                const { data: res } = await sbClient.from('google_reservations')
                    .select('booking_employee, trip_type')
                    .gte('created_at', monthStart);

                if (res && res.length > 0) {
                    const stats = {};
                    res.forEach(r => {
                        const emp = r.booking_employee || 'غير محدد';
                        if (!stats[emp]) stats[emp] = { total: 0, vip: 0 };
                        stats[emp].total++;
                        if ((r.trip_type || '').toLowerCase().includes('vip')) stats[emp].vip++;
                    });

                    const list = document.getElementById('staff-performance-list');
                    const card = document.getElementById('staff-performance-card');
                    list.innerHTML = Object.entries(stats)
                        .sort((a,b) => b[1].total - a[1].total)
                        .map(([name, s]) => `
                            <div class="flex justify-between items-center border-b border-indigo-100 pb-1">
                                <span class="font-bold text-slate-700">${name}</span>
                                <div class="flex gap-2">
                                    <span class="bg-indigo-100 text-indigo-600 px-1.5 py-0.5 rounded font-bold">${s.total} حجز</span>
                                    <span class="bg-amber-100 text-amber-600 px-1.5 py-0.5 rounded font-bold">${s.vip} VIP</span>
                                </div>
                            </div>
                        `).join('');
                    card.classList.remove('hidden');
                }
            } catch (e) {
                console.error('Staff Stats Error:', e);
            }
        }

        // ==========================================
        // غرفة العمليات - تحديث لحظي
        // ==========================================
        let opsRealtimeChannel = null;
        function setupOpsRealtime() {
            if (opsRealtimeChannel) return; // لا تسجّل مرتين
            opsRealtimeChannel = sbClient.channel('ops-realtime')
                .on('postgres_changes', { event: '*', schema: 'public', table: 'trips' }, () => {
                    // تحديث الجدول تلقائياً عند أي تغيير
                    const opsPage = document.getElementById('page-operations');
                    if (opsPage && !opsPage.classList.contains('hidden')) {
                        loadOperations();
                    }
                })
                .subscribe();
        }

        function clearOpsFilter() {
            if(document.getElementById('ops-search')) document.getElementById('ops-search').value = '';
            if(document.getElementById('ops-date-from')) document.getElementById('ops-date-from').value = '';
            if(document.getElementById('ops-date-to')) document.getElementById('ops-date-to').value = '';
            loadOperations();
        }

        async function loadOperations() {
            const list = document.getElementById('ops-table');
            list.innerHTML = '<tr><td colspan="8" class="text-center p-4">جاري التحميل...</td></tr>';
            
            const search = document.getElementById('ops-search')?.value.toLowerCase() || '';
            const fDate = document.getElementById('ops-date-from')?.value || '';
            const tDate = document.getElementById('ops-date-to')?.value || '';

            const { data: trips, error } = await sbClient.from('trips').select(`*, cars:cars!fk_trips_car(brand, model, plate_number), drivers:drivers!fk_trips_driver(name, phone)`).order('created_at', { ascending: false });
            if (error) { list.innerHTML = '<tr><td colspan="8" class="text-center p-4 text-red-500">حدث خطأ</td></tr>'; return; }

            const userIds = trips?.map(t => t.user_id).filter(Boolean) || [];
            let profilesMap = {};
            if (userIds.length) {
                const { data: profiles } = await sbClient.from('profiles').select('id, full_name, phone').in('id', userIds);
                if (profiles) profiles.forEach(p => profilesMap[p.id] = p);
            }

            list.innerHTML = '';
            
            const filteredTrips = (trips || []).filter(t => {
                let matchSearch = true;
                if (search) {
                    const profile = profilesMap[t.user_id] || {};
                    let name = profile.full_name || t.manual_client_name || '';
                    let phone = profile.phone || t.client_phone || '';
                    let notes = t.admin_notes || '';
                    let locs = (t.pickup_location || '') + ' ' + (t.dropoff_location || '');
                    matchSearch = name.toLowerCase().includes(search) || phone.includes(search) || notes.toLowerCase().includes(search) || locs.toLowerCase().includes(search) || String(t.id).includes(search);
                }

                let matchDate = true;
                if (fDate || tDate) {
                    let extractedDateStr = '';
                    if (t.admin_notes) {
                        const dMatch = t.admin_notes.match(/📅\s*([0-9\-/\\]+)/);
                        if (dMatch) extractedDateStr = dMatch[1].trim();
                    }
                    
                    // تحويل التاريخ من النص إذا تم التقاطه، أو استخدام تاريخ إنشاء الطلب كبديل
                    let tripDate;
                    if (extractedDateStr) {
                        tripDate = new Date(extractedDateStr);
                    } else if (t.trip_date) {
                        tripDate = new Date(t.trip_date);
                    } else {
                        tripDate = new Date(t.created_at);
                    }
                    
                    if (!isNaN(tripDate.getTime())) {
                        tripDate.setHours(0,0,0,0);
                        if (fDate) {
                            const fd = new Date(fDate); fd.setHours(0,0,0,0);
                            if (tripDate < fd) matchDate = false;
                        }
                        if (tDate && matchDate) {
                            const td = new Date(tDate); td.setHours(0,0,0,0);
                            if (tripDate > td) matchDate = false;
                        }
                    }
                }
                
                return matchSearch && matchDate;
            });

            if (!filteredTrips.length) { list.innerHTML = '<tr><td colspan="8" class="text-center p-4">لا توجد رحلات مطابقة للفلاتر</td></tr>'; return; }

            filteredTrips.forEach(t => {
                const profile = profilesMap[t.user_id] || { full_name: 'عميل', phone: '-' };

                // البحث عن الاسم والرقم في admin_notes إذا كانت الحقول غير موجودة
                let displayName = profile.full_name || 'عميل';
                let displayPhone = profile.phone || '-';

                // محاولة استخراج البيانات من admin_notes إذا كان الحجز يدوياً
                if (t.admin_notes && t.admin_notes.includes('حجز هاتفي')) {
                    const nameMatch = t.admin_notes.match(/العميل: (.*?)\n/);
                    const phoneMatch = t.admin_notes.match(/رقم: (.*?)\n/);
                    if (nameMatch) displayName = nameMatch[1];
                    if (phoneMatch) displayPhone = phoneMatch[1];
                }

                // إذا وجدت الأعمدة الجديدة في الداتابيز استخدمها
                if (t.manual_client_name) displayName = t.manual_client_name;
                if (t.client_phone) displayPhone = t.client_phone;

                let statusColor = 'bg-amber-100 text-amber-800';
                if (t.status === 'driver_assigned') statusColor = 'bg-blue-100 text-blue-800';
                else if (t.status === 'approved') statusColor = 'bg-green-100 text-green-800';
                else if (t.status === 'completed') statusColor = 'bg-slate-200 text-slate-600';
                else if (t.status === 'trip_ended') statusColor = 'bg-yellow-100 text-yellow-800';

                // إضافة مرحلة الكابتن بجوار الحالة
                let stageText = '';
                if (t.status === 'driver_assigned' && t.stage_status) {
                    const stages = {
                        'new': 'عينت السائق',
                        'garage_pickup': 'استلم من الجراش',
                        'heading_client': 'في الطريق لمحطة الانطلاق',
                        'arrived_client': 'وصل للعميل',
                        'trip_started': 'الرحلة جارية',
                        'post_photos': 'صور بعد الرحلة',
                        'financial_close': 'قفل الحساب',
                        'trip_ended': 'انتهت'
                    };
                    stageText = `<br><span class="text-[9px] text-blue-600 font-bold mt-1 inline-block">⏳ ${stages[t.stage_status] || t.stage_status}</span>`;
                }

                const driverName = t.drivers ? t.drivers.name : '-';
                const carInfo = t.cars ? `${t.cars.brand}` : '-';
                let btns = '';
                if (t.status === 'pending' || t.status === 'approved') btns = `<button onclick="openAssignModal('${t.id}')" class="bg-slate-900 text-white px-2 py-1 rounded text-xs">تعيين</button>`;
                else if (t.status === 'driver_assigned' || t.status === 'trip_ended') btns = `<button onclick="openCompleteModal('${t.id}', ${t.estimated_price}, ${t.distance_km || 0}, ${t.fuel_cost || 0}, ${t.toll_cost || 0})" class="bg-green-600 text-white px-2 py-1 rounded text-xs">إنهاء</button>`;
                // زر عرض صور الفحص لأي رحلة عينها سواق
                if (t.status !== 'pending') btns += ` <button onclick="viewTripPhotos('${t.id}')" class="bg-blue-600 text-white px-2 py-1 rounded text-xs">📸</button>`;

                list.innerHTML += `
                    <tr class="border-b hover:bg-white text-xs">
                        <td class="p-4">#${String(t.id)}</td>
                        <td class="p-4 font-bold text-slate-800">${displayName}<br><span class="text-[10px] text-slate-500">${displayPhone}</span></td>
                        <td class="p-4 min-w-[180px] whitespace-normal leading-relaxed text-slate-600">${t.admin_notes || '-'}</td>
                        <td class="p-4 font-bold text-slate-500">${(t.pickup_location || '-').split(',')[0]} ➝ ${(t.dropoff_location || '-').split(',')[0]}</td>
                        <td class="p-4 font-bold">${driverName} / ${carInfo}</td>
                        <td class="p-4 font-bold text-green-700">${t.estimated_price}</td>
                        <td class="p-4"><span class="px-2 py-1 rounded text-[10px] ${statusColor}">${t.status}</span>${stageText}</td>
                        <td class="p-4">${btns}</td>
                    </tr>
                `;
            });
        }


        async function viewTripPhotos(tripId) {
            const { data: trip } = await sbClient.from('trips').select('pre_inspection_photos, post_inspection_photos').eq('id', tripId).single();
            const pre = trip?.pre_inspection_photos || [];
            const post = trip?.post_inspection_photos || [];

            if (!pre.length && !post.length) {
                alert('لا توجد صور مرفوعة لهذه الرحلة بعد');
                return;
            }

            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black/90 z-[9999] overflow-y-auto p-4';
            modal.innerHTML = `
                <div class="max-w-2xl mx-auto">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-white font-bold text-xl">📸 صور فحص السيارة</h2>
                        <button onclick="this.closest('.fixed').remove()" class="bg-red-600 text-white px-4 py-2 rounded-lg font-bold">✕ إغلاق</button>
                    </div>
                    ${pre.length ? `
                    <h3 class="text-yellow-400 font-bold mb-2">🔑 قبل الرحلة (${pre.length} صورة)</h3>
                    <div class="grid grid-cols-3 gap-2 mb-6">
                        ${pre.map(p => `<div class="aspect-square bg-slate-800 rounded overflow-hidden">
                            <img src="${p.url}" class="w-full h-full object-cover cursor-pointer" onclick="window.open('${p.url}','_blank')" title="${p.id}">
                        </div>`).join('')}
                    </div>` : '<p class="text-slate-400 mb-4">لا توجد صور قبل الرحلة</p>'}
                    ${post.length ? `
                    <h3 class="text-blue-400 font-bold mb-2">🏁 بعد الرحلة (${post.length} صورة)</h3>
                    <div class="grid grid-cols-3 gap-2">
                        ${post.map(p => `<div class="aspect-square bg-slate-800 rounded overflow-hidden">
                            <img src="${p.url}" class="w-full h-full object-cover cursor-pointer" onclick="window.open('${p.url}','_blank')" title="${p.id}">
                        </div>`).join('')}
                    </div>` : '<p class="text-slate-400">لا توجد صور بعد الرحلة</p>'}
                </div>`;
            document.body.appendChild(modal);
        }

        function openCompleteModal(tripId, price, distKm, fuelCost = 0, tollCost = 0) {
            document.getElementById('comp-trip-id').value = tripId;
            document.getElementById('comp-price').value = price;
            document.getElementById('comp-dist-km').value = distKm || 0;
            document.getElementById('comp-wage').value = 0;
            document.getElementById('comp-fuel').value = fuelCost;
            document.getElementById('comp-tolls').value = tollCost;
            document.getElementById('comp-commission').value = 0;
            const maint = Math.round((distKm || 0) * 0.6);
            document.getElementById('comp-maintenance-display').innerText = maint + ' EGP (' + (distKm || 0) + ' km × 0.6)';
            document.getElementById('complete-modal').style.display = 'flex';
            updateCompSummary();
        }

        function updateCompSummary() {
            const price = Number(document.getElementById('comp-price').value) || 0;
            const wage = Number(document.getElementById('comp-wage').value) || 0;
            const fuel = Number(document.getElementById('comp-fuel').value) || 0;
            const tolls = Number(document.getElementById('comp-tolls').value) || 0;
            const commission = Number(document.getElementById('comp-commission').value) || 0;
            const distKm = Number(document.getElementById('comp-dist-km').value) || 0;
            const maint = Math.round(distKm * 0.6);
            const carNet = price - wage - fuel - tolls - commission - maint;
            document.getElementById('sum-wage').innerText = wage + ' EGP';
            document.getElementById('sum-maint').innerText = maint + ' EGP';
            document.getElementById('sum-comm').innerText = commission + ' EGP';
            document.getElementById('sum-ops').innerText = (fuel + tolls) + ' EGP';
            document.getElementById('sum-car').innerText = carNet + ' EGP';
            document.getElementById('sum-car').className = 'font-bold ' + (carNet >= 0 ? 'text-green-700' : 'text-red-600');
        }

        async function confirmComplete() {
            const tripId = document.getElementById('comp-trip-id').value;
            const price = Number(document.getElementById('comp-price').value);
            const wage = Number(document.getElementById('comp-wage').value);
            const fuel = Number(document.getElementById('comp-fuel').value);
            const tolls = Number(document.getElementById('comp-tolls').value);
            const commission = Number(document.getElementById('comp-commission').value);
            const distKm = Number(document.getElementById('comp-dist-km').value);
            const maint = Math.round(distKm * 0.6);
            const carNet = price - wage - fuel - tolls - commission - maint;

            if (!confirm('تأكيد الإنهاء؟')) return;
            await sbClient.from('trips').update({ status: 'completed', final_price: price, driver_wage: wage }).eq('id', tripId);
            const { data: trip } = await sbClient.from('trips').select('driver_id, car_id').eq('id', tripId).single();
            const tripLabel = String(tripId).slice(0, 6);

            // 1. يومية الكابتن → خزنة السواقين
            if (wage > 0) {
                const vid = await getVaultIdByName('خزنة السواقين');
                if (vid) { const { data: v } = await sbClient.from('vaults').select('balance').eq('id', vid).single(); await sbClient.from('vaults').update({ balance: (v.balance || 0) + wage }).eq('id', vid); }
                if (trip.driver_id) await sbClient.from('expenses').insert([{ title: `يومية #${tripLabel}`, amount: wage, category: 'رواتب', related_trip_id: tripId, related_driver_id: trip.driver_id }]);
            }

            // 2. صيانة (km × 0.6) → خزنة الصيانة
            if (maint > 0) {
                const vid = await getVaultIdByName('خزنة الصيانة');
                if (vid) { const { data: v } = await sbClient.from('vaults').select('balance').eq('id', vid).single(); await sbClient.from('vaults').update({ balance: (v.balance || 0) + maint }).eq('id', vid); }
                if (trip.car_id) await sbClient.from('expenses').insert([{ title: `صيانة ${distKm}km #${tripLabel}`, amount: maint, category: 'صيانة', related_trip_id: tripId, related_car_id: trip.car_id }]);
            }

            // 3. عمولة → خزنة العمولات
            if (commission > 0) {
                const vid = await getVaultIdByName('خزنة العمولات');
                if (vid) { const { data: v } = await sbClient.from('vaults').select('balance').eq('id', vid).single(); await sbClient.from('vaults').update({ balance: (v.balance || 0) + commission }).eq('id', vid); }
                const expData = { title: `عمولة #${tripLabel}`, amount: commission, category: 'عمولات', related_trip_id: tripId };
                if (trip.driver_id) expData.related_driver_id = trip.driver_id;
                await sbClient.from('expenses').insert([expData]);
            }

            // 4. بنزين + كروت → مصروف تشغيل (سجل فقط)
            if (fuel > 0 && trip.car_id) await sbClient.from('expenses').insert([{ title: `بنزين #${tripLabel}`, amount: fuel, category: 'تشغيل', related_trip_id: tripId, related_car_id: trip.car_id }]);
            if (tolls > 0 && trip.car_id) await sbClient.from('expenses').insert([{ title: `كروت #${tripLabel}`, amount: tolls, category: 'تشغيل', related_trip_id: tripId, related_car_id: trip.car_id }]);

            // 5. المتبقي → خزنة رواتب السيارات
            if (carNet > 0) {
                const vid = await getVaultIdByName('خزنة رواتب السيارات');
                if (vid) { const { data: v } = await sbClient.from('vaults').select('balance').eq('id', vid).single(); await sbClient.from('vaults').update({ balance: (v.balance || 0) + carNet }).eq('id', vid); }
            }

            document.getElementById('complete-modal').style.display = 'none';
            loadOperations(); loadDashboard(); loadFinance();
        }

        async function loadFinance() {
            const { data: vaults } = await sbClient.from('vaults').select('*');
            const grid = document.getElementById('vaults-grid');
            const select = document.getElementById('gen-exp-vault');
            const modalSelect = document.getElementById('exp-modal-vault');
            grid.innerHTML = ''; select.innerHTML = ''; modalSelect.innerHTML = '';
            if (vaults) {
                // حساب الخزينة الرئيسية = مجموع كل الخزائن الفرعية
                const subVaults = vaults.filter(v => v.name !== 'الخزينة الرئيسية');
                const mainTotal = subVaults.reduce((sum, v) => sum + (Number(v.balance) || 0), 0);
                // تحديث رصيد الخزينة الرئيسية في الداتابيز
                const mainVault = vaults.find(v => v.name === 'الخزينة الرئيسية');
                if (mainVault && mainVault.balance !== mainTotal) {
                    await sbClient.from('vaults').update({ balance: mainTotal }).eq('id', mainVault.id);
                }
                // عرض الخزينة الرئيسية أولاً بلون مميز
                grid.innerHTML += `<div class="glass-panel p-5 border-l-4 border-green-500 bg-green-50"><p class="text-xs font-bold text-green-700 uppercase"><i class="fas fa-university ml-1"></i> الخزينة الرئيسية (إجمالي)</p><h3 class="text-3xl font-black mt-1 text-green-800">${mainTotal} <span class="text-sm font-normal">EGP</span></h3></div>`;
                // عرض الخزائن الفرعية
                const vaultColors = { 'خزنة السواقين': 'blue', 'خزنة رواتب السيارات': 'amber', 'خزنة الصيانة': 'red', 'خزنة العمولات': 'purple' };
                subVaults.forEach(v => {
                    const color = vaultColors[v.name] || 'slate';
                    grid.innerHTML += `<div class="glass-panel p-5 border-l-4 border-${color}-500"><p class="text-xs font-bold text-slate-500 uppercase">${v.name}</p><h3 class="text-2xl font-black mt-1">${v.balance} <span class="text-sm font-normal">EGP</span></h3></div>`;
                    select.innerHTML += `<option value="${v.id}">${v.name}</option>`;
                    modalSelect.innerHTML += `<option value="${v.id}">${v.name}</option>`;
                });
            }
            const { data: reqs } = await sbClient.from('transactions').select('*').eq('status', 'pending');
            const reqList = document.getElementById('deposit-requests-list');
            reqList.innerHTML = '';
            if (!reqs || reqs.length === 0) { reqList.innerHTML = '<p class="text-center text-slate-400 text-sm">لا توجد طلبات</p>'; } else {
                const userIds = reqs.map(r => r.user_id);
                let profilesMap = {};
                if (userIds.length > 0) { const { data: profiles } = await sbClient.from('profiles').select('id, full_name').in('id', userIds); if (profiles) profiles.forEach(p => profilesMap[p.id] = p.full_name); }
                reqs.forEach(r => {
                    const clientName = profilesMap[r.user_id] || 'عميل';
                    reqList.innerHTML += `<div class="bg-white border rounded-lg p-3 flex justify-between items-center mb-2"><div><p class="font-bold text-sm text-slate-800">${clientName}</p><p class="text-green-600 font-bold font-num mt-1">${r.amount} EGP</p></div><div class="flex gap-2"><button onclick="processDeposit('${r.id}', '${r.user_id}', ${r.amount}, true)" class="bg-green-600 text-white px-2 py-1 rounded text-xs">قبول</button><button onclick="processDeposit('${r.id}', null, null, false)" class="bg-red-100 text-red-600 px-2 py-1 rounded text-xs">رفض</button></div></div>`;
                });
            }
        }

        async function processDeposit(txId, userId, amount, isApproved) {
            if (isApproved) {
                if (!confirm(`قبول ${amount}؟`)) return;
                await sbClient.from('transactions').update({ status: 'approved' }).eq('id', txId);
                const { data: profile } = await sbClient.from('profiles').select('wallet_balance').eq('id', userId).single();
                await sbClient.from('profiles').update({ wallet_balance: (profile?.wallet_balance || 0) + Number(amount) }).eq('id', userId);
                const vid = await getMainVaultId();
                const { data: v } = await sbClient.from('vaults').select('balance').eq('id', vid).single();
                await sbClient.from('vaults').update({ balance: (v.balance || 0) + Number(amount) }).eq('id', vid);
            } else { if (!confirm("رفض؟")) return; await sbClient.from('transactions').update({ status: 'rejected' }).eq('id', txId); }
            loadFinance();
        }

        async function addGeneralExpense() {
            const title = document.getElementById('gen-exp-title').value;
            const amount = document.getElementById('gen-exp-amount').value;
            const vaultId = document.getElementById('gen-exp-vault').value;
            if (!title || !amount) return alert("البيانات ناقصة");
            const vid = vaultId === 'main' ? (await getMainVaultId()) : vaultId;
            await sbClient.from('expenses').insert([{ title, amount, category: 'عام', related_vault_id: vid }]);
            const { data: v } = await sbClient.from('vaults').select('balance').eq('id', vid).single();
            await sbClient.from('vaults').update({ balance: (v.balance || 0) - Number(amount) }).eq('id', vid);
            alert("تم"); loadFinance();
        }

        async function getMainVaultId() { const { data } = await sbClient.from('vaults').select('id').eq('name', 'الخزينة الرئيسية').single(); return data?.id; }
        async function getVaultIdByName(name) { const { data } = await sbClient.from('vaults').select('id').eq('name', name).single(); return data?.id; }

        async function loadFleetList() {
            const { data: cars } = await sbClient.from('cars').select('*');
            const { data: drivers } = await sbClient.from('drivers').select('*');
            const carsDiv = document.getElementById('fleet-cars-list');
            if (cars) carsDiv.innerHTML = cars.map(c => `<div onclick="openLedger('car', '${c.id}', '${c.brand} ${c.plate_number}', ${c.monthly_salary || 0})" class="bg-white p-3 border rounded cursor-pointer hover:bg-slate-50 mb-2 font-bold flex justify-between"><span>${c.brand}</span><span>${c.plate_number}</span></div>`).join('');
            const driversDiv = document.getElementById('fleet-drivers-list');
            if (drivers) driversDiv.innerHTML = drivers.map(d => `<div onclick="openLedger('driver', '${d.id}', '${d.name}')" class="bg-white p-3 border rounded cursor-pointer hover:bg-slate-50 mb-2 font-bold">${d.name}</div>`).join('');
        }

        async function openLedger(type, id, name, salary = 0) {
            const view = document.getElementById('ledger-view'); view.innerHTML = 'جاري التحميل...';
            let income = 0; let outcome = 0; let movements = [];
            const { data: exps } = await sbClient.from('expenses').select('*').eq(type === 'car' ? 'related_car_id' : 'related_driver_id', id);

            if (type === 'driver') {
                // إيراد السواق = يوميات الرحلات (category = رواتب)
                if (exps) exps.forEach(e => {
                    if (e.category === 'رواتب') {
                        income += Number(e.amount);
                        movements.push({ date: e.created_at, title: e.title, amount: Number(e.amount), type: 'in' });
                    } else {
                        outcome += Number(e.amount);
                        movements.push({ date: e.created_at, title: e.title, amount: -Number(e.amount), type: 'out' });
                    }
                });
            } else {
                // سيارة
                if (exps) exps.forEach(e => { outcome += Number(e.amount); movements.push({ date: e.created_at, title: e.title, amount: -Number(e.amount), type: 'out' }); });
                const { data: trips } = await sbClient.from('trips').select('*').eq('car_id', id).eq('status', 'completed');
                if (trips) trips.forEach(t => { income += Number(t.final_price); movements.push({ date: t.created_at, title: 'إيراد', amount: Number(t.final_price), type: 'in' }); });
            }

            movements.sort((a, b) => new Date(b.date) - new Date(a.date));
            const net = income - outcome;

            let extraBtns = '';
            if (type === 'car') {
                extraBtns = `<button onclick="payCarSalary('${id}', ${salary})" class="w-full bg-purple-600 text-white py-2 rounded mt-3 font-bold">سداد قسط (${salary})</button>`;
            } else {
                // أزرار السواق: خصم/سلف + تسوية
                extraBtns = `
                    <div class="bg-blue-50 p-3 rounded-lg border border-blue-200 mt-3 space-y-2">
                        <p class="font-bold text-blue-800 text-sm">📝 تسجيل خصم / سلفة</p>
                        <select id="drv-deduct-type" class="input-std text-xs">
                            <option value="خصم">خصم</option>
                            <option value="سلفة">سلفة</option>
                            <option value="غرامة">غرامة</option>
                        </select>
                        <input type="text" id="drv-deduct-reason" placeholder="السبب" class="input-std text-xs">
                        <input type="number" id="drv-deduct-amount" placeholder="المبلغ" class="input-std text-xs">
                        <button onclick="addDriverDeduction('${id}', '${name}')" class="w-full bg-red-600 text-white py-1.5 rounded text-xs font-bold">تسجيل</button>
                    </div>
                    <button onclick="settleDriver('${id}', '${name}', ${net})" class="w-full bg-green-600 text-white py-2 rounded mt-3 font-bold">💰 تسوية / قبض (المستحق: ${net} EGP)</button>
                `;
            }

            view.innerHTML = `<h3 class="font-bold text-xl mb-4 border-b pb-2">${name}</h3>
                <div class="grid grid-cols-3 gap-2 mb-4 text-center text-xs">
                    <div class="bg-green-50 p-2 rounded"><p>مستحق (يوميات)</p><p class="font-bold text-green-700">${income}</p></div>
                    <div class="bg-red-50 p-2 rounded"><p>خصومات/سلف</p><p class="font-bold text-red-700">${outcome}</p></div>
                    <div class="bg-slate-100 p-2 rounded"><p>صافي مستحق</p><p class="font-bold ${net >= 0 ? 'text-green-700' : 'text-red-600'}">${net}</p></div>
                </div>
                <button onclick="openExpenseModal('${type}', '${id}')" class="w-full bg-red-600 text-white py-2 rounded mb-2 text-sm">تسجيل حركة يدوية</button>
                ${extraBtns}
                <div class="mt-4 space-y-1 max-h-48 overflow-y-auto">
                    <p class="font-bold text-xs text-slate-500 mb-2">📋 سجل الحركات:</p>
                    ${movements.map(m => `<div class="flex justify-between text-xs border-b pb-1 py-1">
                        <span class="text-slate-600">${m.title}</span>
                        <div class="flex gap-3">
                            <span class="${m.type === 'in' ? 'text-green-600' : 'text-red-600'} font-bold">${m.amount}</span>
                            <span class="text-slate-400 text-[10px]">${new Date(m.date).toLocaleDateString('ar-EG')}</span>
                        </div>
                    </div>`).join('')}
                </div>`;
        }

        async function payCarSalary(carId, amount) {
            if (!confirm(`سداد ${amount}؟`)) return;
            const vid = await getVaultIdByName('خزنة رواتب السيارات');
            if (!vid) { alert('خزنة رواتب السيارات غير موجودة'); return; }
            await sbClient.from('expenses').insert([{ title: 'قسط/راتب شهري', amount: amount, category: 'رواتب سيارات', related_car_id: carId, related_vault_id: vid }]);
            const { data: v } = await sbClient.from('vaults').select('balance').eq('id', vid).single();
            await sbClient.from('vaults').update({ balance: (v.balance || 0) - amount }).eq('id', vid);
            alert("تم السداد ✅ تم الخصم من خزنة رواتب السيارات"); loadFinance(); openLedger('car', carId, '...');
        }

        async function addDriverDeduction(driverId, driverName) {
            const deductType = document.getElementById('drv-deduct-type').value;
            const reason = document.getElementById('drv-deduct-reason').value;
            const amount = Number(document.getElementById('drv-deduct-amount').value);
            if (!reason || !amount || amount <= 0) return alert('أدخل السبب والمبلغ');
            // خصم من خزنة السواقين
            const vid = await getVaultIdByName('خزنة السواقين');
            if (vid) {
                const { data: v } = await sbClient.from('vaults').select('balance').eq('id', vid).single();
                await sbClient.from('vaults').update({ balance: (v.balance || 0) - amount }).eq('id', vid);
            }
            await sbClient.from('expenses').insert([{ title: `${deductType}: ${reason}`, amount, category: deductType, related_driver_id: driverId, related_vault_id: vid }]);
            alert(`تم تسجيل ${deductType} بمبلغ ${amount} EGP وتم الخصم من خزنة السواقين`);
            loadFinance(); openLedger('driver', driverId, driverName);
        }

        async function settleDriver(driverId, driverName, netAmount) {
            if (netAmount <= 0) return alert('لا يوجد مبلغ مستحق للقبض');
            const payAmount = prompt(`المستحق: ${netAmount} EGP\nأدخل المبلغ المراد قبضه:`, netAmount);
            if (!payAmount || Number(payAmount) <= 0) return;
            const pay = Number(payAmount);
            if (!confirm(`تأكيد قبض ${pay} EGP للكابتن ${driverName}؟`)) return;
            // خصم من خزنة السواقين
            const vid = await getVaultIdByName('خزنة السواقين');
            if (!vid) { alert('خزنة السواقين غير موجودة'); return; }
            const { data: v } = await sbClient.from('vaults').select('balance').eq('id', vid).single();
            await sbClient.from('vaults').update({ balance: (v.balance || 0) - pay }).eq('id', vid);
            // تسجيل التسوية كمصروف على السواق
            await sbClient.from('expenses').insert([{ title: `تسوية / قبض ${new Date().toLocaleDateString('ar-EG')}`, amount: pay, category: 'تسوية', related_driver_id: driverId, related_vault_id: vid }]);
            alert(`تم قبض ${pay} EGP ✅\n${pay < netAmount ? `متبقي في حسابه: ${netAmount - pay} EGP` : 'تم التسوية بالكامل'}`);
            loadFinance(); openLedger('driver', driverId, driverName);
        }

        async function openExpenseModal(type, id) { document.getElementById('expense-modal').style.display = 'flex'; document.getElementById('exp-target-type').value = type; document.getElementById('exp-target-id').value = id; }
        async function confirmExpense() {
            const type = document.getElementById('exp-target-type').value; const id = document.getElementById('exp-target-id').value; const title = document.getElementById('exp-modal-title').value; const amount = document.getElementById('exp-modal-amount').value; const vaultId = document.getElementById('exp-modal-vault').value;
            if (!title || !amount) return alert("ناقصة");
            const mainVaultId = await getMainVaultId();
            const insertData = { title, amount, category: 'يدوي', related_vault_id: vaultId };
            if (type === 'car') insertData.related_car_id = id; if (type === 'driver') insertData.related_driver_id = id;
            const { error } = await sbClient.from('expenses').insert([insertData]);
            if (!error) { const { data: mainV } = await sbClient.from('vaults').select('balance').eq('id', mainVaultId).single(); await sbClient.from('vaults').update({ balance: (mainV.balance || 0) - Number(amount) }).eq('id', mainVaultId); if (vaultId !== 'main' && vaultId !== mainVaultId) { const { data: subV } = await sbClient.from('vaults').select('balance').eq('id', vaultId).single(); await sbClient.from('vaults').update({ balance: (subV.balance || 0) - Number(amount) }).eq('id', vaultId); } document.getElementById('expense-modal').style.display = 'none'; alert("تم"); openLedger(type, id, '...'); loadFinance(); } else { alert(error.message); }
        }

        async function loadCRM() {
            const list = document.getElementById('crm-table'); const { data: profiles } = await sbClient.from('profiles').select('*'); list.innerHTML = ''; if (!profiles || profiles.length === 0) list.innerHTML = '<tr><td colspan="4" class="text-center p-4">لا يوجد</td></tr>'; else profiles.forEach(p => { list.innerHTML += `<tr class="border-b bg-white"><td class="p-4 font-bold text-slate-700">${p.full_name || '-'}</td><td class="p-4 text-slate-500">${p.phone || '-'}</td><td class="p-4 font-bold ${p.wallet_balance < 0 ? 'text-red-500' : 'text-green-600'}">${p.wallet_balance || 0}</td><td class="p-4 text-xs text-slate-400">${new Date(p.created_at).toLocaleDateString()}</td></tr>`; });
        }
        async function loadPricing() { const { data } = await sbClient.from('pricing_tiers').select('*').order('car_type').order('min_km'); document.getElementById('pricing-list').innerHTML = data.map(r => `<div class="bg-white p-3 border rounded mb-2 flex justify-between items-center"><div class="flex-1"><span class="font-bold">${r.car_type}</span> <span class="text-xs text-slate-500 mx-2">(${r.min_km}-${r.max_km} km)</span> <span class="text-xs text-slate-500">فتح: ${r.base_price}</span></div><span class="font-bold text-green-700 mx-3">${r.price_per_km}/km</span><button onclick="deletePricingTier(${r.id})" class="text-red-500 hover:text-red-700 hover:bg-red-50 w-8 h-8 rounded-lg flex items-center justify-center transition"><i class="fas fa-trash-alt text-sm"></i></button></div>`).join(''); }
        async function deletePricingTier(id) { if (!confirm('هل تريد حذف هذه الشريحة؟')) return; const { error } = await sbClient.from('pricing_tiers').delete().eq('id', id); if (error) { alert('خطأ: ' + error.message); return; } alert('🗑️ تم الحذف'); loadPricing(); }
        async function addPricingTier() { const type = document.getElementById('rule-type').value, min = document.getElementById('rule-min').value, max = document.getElementById('rule-max').value, base = document.getElementById('rule-base').value, km = document.getElementById('rule-km').value; if (!min || !max || !base || !km) { alert('أكمل البيانات'); return; } const { error } = await sbClient.from('pricing_tiers').insert([{ car_type: type, min_km: min, max_km: max, base_price: base, price_per_km: km }]); if (error) { alert('خطأ: ' + error.message); return; } alert('✅ تم الحفظ'); loadPricing(); }
        async function openAssignModal(id) { document.getElementById('modal-trip-id').value = id; document.getElementById('assign-modal').style.display = 'flex'; const { data: d } = await sbClient.from('drivers').select('*'); const { data: c } = await sbClient.from('cars').select('*'); const dSel = document.getElementById('modal-driver'); dSel.innerHTML = ''; d.forEach(x => dSel.innerHTML += `<option value="${x.id}">${x.name}</option>`); const cSel = document.getElementById('modal-car'); cSel.innerHTML = ''; c.forEach(x => cSel.innerHTML += `<option value="${x.id}">${x.brand}</option>`); }
        async function confirmAssign() {
            const tid = document.getElementById('modal-trip-id').value;
            const did = document.getElementById('modal-driver').value;
            const cid = document.getElementById('modal-car').value;
            const note = document.getElementById('modal-note').value;

            // جلب الملاحظات الحالية أولاً حتى لا نفقد بيانات الرحلة
            const { data: existingTrip } = await sbClient.from('trips').select('admin_notes, pickup_location, dropoff_location, estimated_price').eq('id', tid).single();
            const existingNotes = existingTrip?.admin_notes || '';

            // دمج الملاحظات القديمة مع الجديدة
            let updatedNotes = existingNotes;
            if (note && note.trim()) {
                updatedNotes = existingNotes ? existingNotes + '\n--- ملاحظات التعيين ---\n' + note : note;
            }

            await sbClient.from('trips').update({
                driver_id: did,
                car_id: cid,
                admin_notes: updatedNotes,
                status: 'driver_assigned'
            }).eq('id', tid);

            // جلب بيانات الكابتن والسيارة
            const { data: driverInfo } = await sbClient.from('drivers').select('name, phone').eq('id', did).single();
            const { data: carInfo } = await sbClient.from('cars').select('brand, model, plate_number').eq('id', cid).single();

            // إرسال رسالة تنبيه في الشات للكابتن
            const pickup = (existingTrip?.pickup_location || '').split(',')[0];
            const dropoff = (existingTrip?.dropoff_location || '').split(',')[0];
            const price = existingTrip?.estimated_price || 0;

            await sbClient.from('chat_messages').insert([{
                trip_id: tid,
                sender_role: 'admin',
                sender_id: 'admin',
                sender_name: 'الإدارة',
                message: `🎯 مرحباً كابتن ${driverInfo?.name || ''}!\n\nتم تعيينك على رحلة جديدة:\n📍 من: ${pickup}\n🏁 إلى: ${dropoff}\n💰 قيمة الرحلة: ${price} EGP\n🚗 السيارة: ${carInfo?.brand || ''} ${carInfo?.model || ''} (${carInfo?.plate_number || ''})\n\n✅ تواصل مع العميل من خلال الدردشة فقط\n📸 لا تنسى تصوير السيارة قبل الخروج من الجراش`,
                message_type: 'system'
            }]);

            // 🌐 محاولة إرسال التعيين لـ Google Sheets للتزامن وإرسال الواتساب
            try {
                const APPS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbyInsDC7MKcsfJWVwYpl5pFmiDp5XdkSF5Pi1MSJfSbKQPTp0M8F3aUhb9QHmBdbYutjA/exec';
                // Fire and forget (لا نعطل الواجهة لو فشل الشيت)
                fetch(APPS_SCRIPT_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'text/plain' },
                    body: JSON.stringify({
                        action: 'assignDriver',
                        webId: tid, // ID رحلة السايت
                        driverName: driverInfo?.name || '',
                        driverPhone: driverInfo?.phone || ''
                    })
                }).catch(e => console.error("Sheet Sync Error:", e));
            } catch (err) {}

            document.getElementById('assign-modal').style.display = 'none';
            alert(`✅ تم تعيين الكابتن ${driverInfo?.name || ''} وإرسال إشعار له`);
            loadOperations();
        }

        async function addCarPrompt() { const b = prompt("الماركة:"); const p = prompt("اللوحة:"); const s = prompt("الراتب:"); if (b) { await sbClient.from('cars').insert([{ brand: b, plate_number: p, monthly_salary: s || 0 }]); loadFleetList(); } }
        async function addDriverPrompt() { const n = prompt("الاسم:"); const p = prompt("هاتف:"); if (n) { await sbClient.from('drivers').insert([{ name: n, phone: p }]); loadFleetList(); } }

        new Chart(document.getElementById('tripsChart'), { type: 'bar', data: { labels: ['S', 'M', 'T', 'W', 'T', 'F', 'S'], datasets: [{ label: 'الرحلات', data: [5, 8, 12, 7, 15, 10, 9], backgroundColor: '#3b82f6', borderRadius: 4 }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, display: false }, x: { grid: { display: false } } } } });

        // --- وظيفة إضافة حجز يدوي ---
        async function submitManualTrip() {
            // 1. جمع البيانات
            const name = document.getElementById('manual-name').value;
            const phone = document.getElementById('manual-phone').value;
            const pickup = document.getElementById('manual-pickup').value;
            const dropoff = document.getElementById('manual-dropoff').value;
            const date = document.getElementById('manual-date').value;
            const time = document.getElementById('manual-time').value;
            const price = document.getElementById('manual-price').value;
            const notes = document.getElementById('manual-notes').value;

            const clientType = document.getElementById('manual-client-type').value;
            const carType = document.getElementById('manual-car-type').value;
            const tripType = document.getElementById('manual-trip-type').value;
            const passengers = document.getElementById('manual-passengers').value;
            const luggage = document.getElementById('manual-luggage').value;

            // 2. التحقق
            if (!name || !phone || !pickup || !dropoff || !price) {
                alert("يرجى ملء جميع البيانات الأساسية (الاسم، الهاتف، العنوان، السعر)");
                return;
            }

            // 3. إنشاء/ربط حساب العميل برقم هاتفه
            const rawPhone = phone.replace(/\D/g, '');
            const fakeEmail = rawPhone + '@24seven-client.app';
            const password = rawPhone.slice(-6);
            let clientUserId = null;

            // أولاً تحقق من وجود الحساب
            try {
                const { data: existingProfile } = await sbClient.from('profiles').select('id').eq('phone', rawPhone).maybeSingle();
                if (existingProfile) {
                    clientUserId = existingProfile.id;
                    await sbClient.from('profiles').update({ full_name: name }).eq('id', clientUserId);
                } else {
                    // إنشاء حساب جديد
                    const { data: signUpData } = await sbClient.auth.signUp({ email: fakeEmail, password });
                    if (signUpData?.user) {
                        clientUserId = signUpData.user.id;
                        await sbClient.from('profiles').upsert({ id: clientUserId, full_name: name, phone: rawPhone, wallet_balance: 0 });
                    }
                }
            } catch (e) { console.log('خطأ منوع إنشاء الحساب:', e); }

            // 4. تجميع الملاحظات
            const fullNotes = `حجز هاتفي 📞
العميل: ${name} (${clientType})
رقم: ${phone}
سيارة: ${carType} | رحلة: ${tripType}
ركاب: ${passengers} | شنط: ${luggage}
التاريخ: ${date} | الوقت: ${time}
ملاحظات إضافية: ${notes}`;

            try {
                // 5. الإرسال إلى Supabase مع ربط user_id
                const { error } = await sbClient.from('trips').insert([{
                    user_id: clientUserId,
                    pickup_location: pickup,
                    dropoff_location: dropoff,
                    estimated_price: Number(price),
                    status: 'pending',
                    admin_notes: fullNotes,
                    car_type: carType
                }]);

                if (error) throw error;

                // إرسال إلى جوجل شيت
                try {
                    sendToAdminSheet({
                        tripDate: date,
                        tripTime: time,
                        clientName: name,
                        phone: rawPhone,
                        whatsapp: rawPhone,
                        pickup: pickup,
                        dropoff: dropoff,
                        passengers: passengers,
                        bags: luggage,
                        carType: carType,
                        clientStatus: clientType === 'vip' ? 'VIP' : (clientType === 'returning' ? 'عميل قديم' : 'عميل جديد'),
                        price: price,
                        email: '',
                        notes: notes,
                        tripType: tripType,
                        enteredBy: 'موظف'
                    });
                } catch (se) { console.log('Sheet error:', se); }

                // 6. نجاح
                const successMsg = clientUserId
                    ? `✅ تم تسجيل الحجز بنجاح!\n\n📱 تم إنشاء/ربط حساب العميل:\nرقم الهاتف: ${phone}\nكلمة المرور: ${password}\n\nأخبر العميل بهذه البيانات للدخول على الموقع.`
                    : '✅ تم تسجيل الحجز بنجاح';
                alert(successMsg);
                document.getElementById('manual-trip-modal').style.display = 'none';

                // تفريغ الحقول
                document.getElementById('manual-name').value = '';
                document.getElementById('manual-phone').value = '';
                document.getElementById('manual-pickup').value = '';
                document.getElementById('manual-dropoff').value = '';
                document.getElementById('manual-price').value = '';

                loadOperations();
                loadDashboard();


            } catch (err) {
                console.error(err);
                alert("حدث خطأ أثناء الحفظ: " + err.message);
            }
        }

        // ==========================================
        // نظام الدردشة - الإدارة
        // ==========================================
        let adminCurrentTripId = null;
        let adminChatSub = null;

        async function loadAdminChats() {
            const list = document.getElementById('admin-chats-list');
            list.innerHTML = '<p class="text-center text-gray-400 p-6"><i class="fas fa-spinner fa-spin"></i></p>';

            const { data: trips } = await sbClient.from('trips')
                .select('*, drivers:drivers!fk_trips_driver(name), cars:cars!fk_trips_car(brand)')
                .eq('status', 'driver_assigned')
                .order('created_at', { ascending: false });

            if (!trips || trips.length === 0) {
                list.innerHTML = '<p class="text-center text-gray-400 p-6">لا توجد محادثات نشطة</p>';
                return;
            }

            const userIds = trips.map(t => t.user_id).filter(Boolean);
            let profilesMap = {};
            if (userIds.length > 0) {
                const { data: profiles } = await sbClient.from('profiles').select('id, full_name').in('id', userIds);
                if (profiles) profiles.forEach(p => profilesMap[p.id] = p);
            }

            let html = '';
            for (const t of trips) {
                let clientName = profilesMap[t.user_id]?.full_name || 'عميل';
                if (t.manual_client_name) clientName = t.manual_client_name;
                if (t.admin_notes && t.admin_notes.includes('حجز هاتفي')) {
                    const nm = t.admin_notes.match(/العميل: (.*?)[\n(]/);
                    if (nm) clientName = nm[1].trim();
                }
                const driverName = t.drivers?.name || 'كابتن';

                const { data: lastMsg } = await sbClient.from('chat_messages')
                    .select('message, sender_role, created_at').eq('trip_id', t.id)
                    .order('created_at', { ascending: false }).limit(1);
                const preview = lastMsg?.[0]?.message || 'لا رسائل';
                const roleLabel = lastMsg?.[0]?.sender_role === 'client' ? 'العميل' : lastMsg?.[0]?.sender_role === 'driver' ? 'الكابتن' : lastMsg?.[0]?.sender_role === 'admin' ? 'أنت' : '';

                const isActive = adminCurrentTripId == t.id;
                html += `
                <div onclick="openAdminChat('${t.id}', '${clientName}', '${driverName}', '${(t.pickup_location || '').split(',')[0]}', '${(t.dropoff_location || '').split(',')[0]}')" 
                     class="p-3 cursor-pointer hover:bg-blue-50 transition ${isActive ? 'bg-blue-50 border-r-4 border-blue-500' : ''}">
                    <div class="flex justify-between items-start">
                        <div>
                            <p class="font-bold text-sm text-gray-800">👤 ${clientName}</p>
                            <p class="text-[10px] text-gray-400">🚗 ${driverName}</p>
                        </div>
                    </div>
                    <p class="text-xs text-gray-500 mt-1 truncate">${roleLabel ? roleLabel + ': ' : ''}${preview}</p>
                </div>`;
            }
            list.innerHTML = html;
        }

        async function openAdminChat(tripId, clientName, driverName, from, to) {
            adminCurrentTripId = tripId;
            document.getElementById('admin-chat-header').innerHTML = `
                <div class="flex justify-between items-center w-full">
                    <div>
                        <p class="font-bold text-gray-700">👤 ${clientName} ↔ 🚗 ${driverName}</p>
                        <p id="admin-chat-route-text" class="text-xs text-gray-400">${from} ➝ ${to}</p>
                    </div>
                    <button onclick="openDestChangeModal('${tripId}', '${to}')" class="bg-amber-100 text-amber-700 hover:bg-amber-200 px-3 py-1.5 rounded-lg text-xs font-bold border border-amber-200 transition flex items-center gap-1">
                        <i class="fas fa-edit"></i> تعديل الوجهة والسعر
                    </button>
                </div>`;
            document.getElementById('admin-chat-input-bar').style.display = 'flex';

            await loadAdminChatMessages(tripId);
            subscribeAdminChat(tripId);
            loadAdminChats(); // refresh list highlighting
        }

        async function loadAdminChatMessages(tripId) {
            const container = document.getElementById('admin-chat-messages');
            const { data: messages } = await sbClient.from('chat_messages').select('*').eq('trip_id', tripId).order('created_at', { ascending: true });
            container.innerHTML = '';
            if (!messages || messages.length === 0) {
                container.innerHTML = '<p class="text-center text-gray-400 py-8">لا توجد رسائل بعد</p>';
                return;
            }
            messages.forEach(m => appendAdminMsg(m));
            container.scrollTop = container.scrollHeight;
        }

        function appendAdminMsg(msg) {
            const container = document.getElementById('admin-chat-messages');
            const placeholder = container.querySelector('p.text-center');
            if (placeholder) placeholder.remove();

            const div = document.createElement('div');
            div.style.animation = 'fadeIn 0.3s ease';
            div.style.maxWidth = '80%';
            div.style.padding = '8px 14px';
            div.style.borderRadius = '12px';
            div.style.fontSize = '0.85rem';
            div.style.lineHeight = '1.5';
            div.style.wordWrap = 'break-word';

            if (msg.sender_role === 'client') {
                div.style.background = '#fef3c7';
                div.style.alignSelf = 'flex-start';
                div.innerHTML = `<span style="font-size:10px;color:#92400e;display:block;margin-bottom:2px">👤 العميل: ${msg.sender_name}</span>`;
            } else if (msg.sender_role === 'driver') {
                div.style.background = '#dbeafe';
                div.style.alignSelf = 'flex-end';
                div.innerHTML = `<span style="font-size:10px;color:#1e40af;display:block;margin-bottom:2px">🚗 الكابتن: ${msg.sender_name}</span>`;
            } else if (msg.sender_role === 'admin') {
                div.style.background = '#ede9fe';
                div.style.alignSelf = 'center';
                div.style.textAlign = 'center';
                div.style.border = '1px solid #c4b5fd';
                div.innerHTML = `<span style="font-size:10px;color:#6d28d9;display:block;margin-bottom:2px">🛡️ الإدارة</span>`;
            } else {
                div.style.background = '#f1f5f9';
                div.style.alignSelf = 'center';
            }

            if (msg.message_type === 'location') {
                div.innerHTML += `📍 <a href="https://maps.google.com/?q=${msg.location_lat},${msg.location_lng}" target="_blank" style="color:#2563eb;text-decoration:underline">فتح الموقع في خرائط جوجل</a>`;
            } else if (msg.message_type === 'admin_request' && msg.message.includes('يطلب تغيير الوجهة إلى:')) {
                const match = msg.message.match(/إلى:\s*(.*)/);
                const newD = match ? match[1].trim() : '';
                div.innerHTML += `<div class="bg-orange-50 p-2 rounded border border-orange-200 mt-1">
                    <p class="font-bold text-orange-800 text-xs mb-2 text-center">🚨 طلب تغيير وجهة</p>
                    <p class="text-xs text-orange-700 mb-3 text-center">الكابتن يطلب تغيير الوجهة إلى:<br><strong>${newD}</strong></p>
                    <div class="flex gap-2 justify-center">
                        <button onclick="respondDestChange('${msg.trip_id}', '${newD}', true)" class="bg-green-600 text-white px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-green-700 w-full">✅ موافقة</button>
                        <button onclick="respondDestChange('${msg.trip_id}', '${newD}', false)" class="bg-red-600 text-white px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-red-700 w-full">❌ رفض</button>
                    </div>
                </div>`;
            } else {
                div.innerHTML += msg.message;
            }

            const time = document.createElement('span');
            time.style.cssText = 'display:block;font-size:9px;margin-top:4px;opacity:0.5';
            time.textContent = new Date(msg.created_at).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' });
            div.appendChild(time);

            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
        }

        async function sendAdminMessage() {
            const input = document.getElementById('admin-chat-input');
            const message = input.value.trim();
            if (!message) return;
            input.value = '';
            try {
                if (adminChatMode === 'support' && adminCurrentSupportUserId) {
                    // إرسال رد خدمة العملاء
                    await sbClient.from('support_chats').insert([{
                        user_id: adminCurrentSupportUserId,
                        sender_role: 'admin',
                        message: message
                    }]);
                    openSupportChat(adminCurrentSupportUserId, document.getElementById('admin-chat-header').querySelector('p')?.textContent || 'عميل');
                } else if (adminCurrentTripId) {
                    // إرسال رسالة رحلة عادي
                    await sbClient.from('chat_messages').insert([{
                        trip_id: adminCurrentTripId,
                        sender_role: 'admin',
                        sender_id: 'admin',
                        sender_name: 'الإدارة',
                        message: message,
                        message_type: 'text'
                    }]);
                }
            } catch (error) {
                console.error('Error sending message:', error);
                alert('فشل إرسال الرسالة');
            }
        }

        // ==========================================
        // خدمة العملاء (Support Chat)
        // ==========================================
        let adminChatMode = 'trip'; // 'trip' or 'support'
        let adminCurrentSupportUserId = null;
        let globalSupportSub = null;

        function setupSupportRealtime() {
            if (globalSupportSub) return;
            globalSupportSub = sbClient.channel('global-support-chats')
                .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'support_chats' }, (payload) => {
                    const msg = payload.new;
                    // إذا كان المرسل هو العميل
                    if (msg.sender_role === 'client') {
                        if (adminChatMode === 'support' && adminCurrentSupportUserId === msg.user_id) {
                            // إذا المشرف فاتح شات هذا العميل تحديداً
                            const container = document.getElementById('admin-chat-messages');
                            if (container) {
                                if (container.innerHTML.includes('لا توجد رسائل')) container.innerHTML = '';
                                const div = document.createElement('div');
                                div.style.cssText = `max-width:80%;padding:10px 14px;border-radius:12px;font-size:0.85rem;line-height:1.5;word-wrap:break-word;margin-bottom:4px;background:#ffffff;border:1px solid #e5e7eb;align-self:flex-start;`;
                                div.innerHTML = `
                                    <p class="text-slate-800" style="white-space: pre-wrap;">${msg.message}</p>
                                    <p class="text-[9px] text-gray-400 mt-1">${new Date(msg.created_at).toLocaleTimeString('ar-EG', {hour: '2-digit', minute:'2-digit'})}</p>
                                `;
                                container.appendChild(div);
                                container.scrollTop = container.scrollHeight;
                            }
                            // نحدث قائمة الجنب بصمت
                            loadSupportChatsSilent();
                        } else {
                            // إشعار
                            const badge = document.getElementById('support-unread-badge');
                            if (badge) {
                                badge.textContent = '!';
                                badge.classList.remove('hidden');
                                badge.classList.add('animate-bounce');
                                setTimeout(() => badge.classList.remove('animate-bounce'), 3000);
                            }
                            // تحديث القائمة لو المشرف في صفحة دعم العملاء
                            if (adminChatMode === 'support' && !adminCurrentSupportUserId) {
                                loadSupportChats();
                            }
                            
                            try {
                                const audio = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
                                audio.play().catch(e => {});
                            } catch(e) {}
                        }
                    }
                })
                .subscribe();
        }

        async function loadSupportChatsSilent() {
            // تحديث خفي للقائمة بدون إظهار لودينج
            const { data: msgs } = await sbClient.from('support_chats')
                .select('user_id, message, created_at, sender_role')
                .order('created_at', { ascending: false });
            if (!msgs || msgs.length === 0) return;
            
            const byUser = {};
            for (const m of msgs) {
                if (!byUser[m.user_id]) byUser[m.user_id] = { uid: m.user_id, last: m.message, time: m.created_at, unread: 0 };
                if (m.sender_role === 'client') byUser[m.user_id].unread++;
            }
            const userIds = Object.keys(byUser);
            if (userIds.length > 0) {
                const { data: profiles } = await sbClient.from('profiles').select('id, full_name').in('id', userIds);
                if (profiles) profiles.forEach(p => { if (byUser[p.id]) byUser[p.id].name = p.full_name || p.id.slice(0, 8); });
            }
            const list = document.getElementById('admin-support-list');
            if(list) {
                list.innerHTML = Object.values(byUser).map(u => `
                    <div onclick="openSupportChat('${u.uid}', '${(u.name || u.uid.slice(0, 8)).replace(/'/g, '')}')"
                         class="p-4 cursor-pointer hover:bg-amber-50 transition border-b border-gray-100 ${adminCurrentSupportUserId === u.uid ? 'bg-amber-50 border-r-4 border-amber-500' : ''}">
                        <div class="flex justify-between items-center">
                            <p class="font-bold text-sm text-gray-800">${u.name || u.uid.slice(0, 8)}</p>
                            <span class="text-[9px] text-gray-400">${new Date(u.time).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                        <p class="text-xs text-gray-500 mt-1 truncate">${u.last}</p>
                    </div>`).join('');
            }
        }

        function switchChatTab(tab) {
            adminChatMode = tab;
            const tripTab = document.getElementById('tab-trip-chat');
            const supportTab = document.getElementById('tab-support-chat');
            const tripList = document.getElementById('chat-list-trip');
            const supportList = document.getElementById('chat-list-support');

            // إعادة ضبط نافذة المحادثة
            document.getElementById('admin-chat-messages').innerHTML = '<p class="text-center text-gray-400 py-12">اختر محادثة من القائمة</p>';
            document.getElementById('admin-chat-header').innerHTML = '<p class="font-bold text-gray-700">اختر محادثة</p>';
            document.getElementById('admin-chat-input-bar').style.display = 'none';

            if (tab === 'trip') {
                tripList.classList.remove('hidden');
                supportList.classList.add('hidden');
                tripTab.className = 'px-4 py-1.5 rounded-md text-sm font-bold bg-white shadow text-blue-700 transition';
                supportTab.className = 'px-4 py-1.5 rounded-md text-sm font-bold text-gray-500 hover:bg-white transition relative';
                loadAdminChats();
            } else {
                tripList.classList.add('hidden');
                supportList.classList.remove('hidden');
                supportTab.className = 'px-4 py-1.5 rounded-md text-sm font-bold bg-white shadow text-amber-700 transition';
                tripTab.className = 'px-4 py-1.5 rounded-md text-sm font-bold text-gray-500 hover:bg-white transition';
                loadSupportChats();
            }
        }

        async function loadSupportChats() {
            const list = document.getElementById('admin-support-list');
            list.innerHTML = '<p class="text-center text-gray-400 text-xs p-6">جاري التحميل...</p>';

            const { data: msgs } = await sbClient.from('support_chats')
                .select('user_id, message, created_at, sender_role')
                .order('created_at', { ascending: false });

            if (!msgs || msgs.length === 0) {
                list.innerHTML = '<p class="text-center text-gray-400 text-xs p-6">لا توجد رسائل دعم</p>';
                return;
            }

            // تجميع حسب user_id
            const byUser = {};
            for (const m of msgs) {
                if (!byUser[m.user_id]) {
                    byUser[m.user_id] = { uid: m.user_id, last: m.message, time: m.created_at, unread: 0 };
                }
                if (m.sender_role === 'client') byUser[m.user_id].unread++;
            }

            // جلب أسماء العملاء
            const userIds = Object.keys(byUser);
            if (userIds.length > 0) {
                const { data: profiles } = await sbClient.from('profiles').select('id, full_name').in('id', userIds);
                if (profiles) profiles.forEach(p => {
                    if (byUser[p.id]) byUser[p.id].name = p.full_name || p.id.slice(0, 8);
                });
            }

            list.innerHTML = Object.values(byUser).map(u => `
                <div onclick="openSupportChat('${u.uid}', '${(u.name || u.uid.slice(0, 8)).replace(/'/g, '')}')"
                     class="p-4 cursor-pointer hover:bg-amber-50 transition border-b border-gray-100 ${adminCurrentSupportUserId === u.uid ? 'bg-amber-50 border-r-4 border-amber-500' : ''}">
                    <div class="flex justify-between items-center">
                        <p class="font-bold text-sm text-gray-800">${u.name || u.uid.slice(0, 8)}</p>
                        <span class="text-[9px] text-gray-400">${new Date(u.time).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <p class="text-xs text-gray-500 mt-1 truncate">${u.last}</p>
                </div>`).join('');
        }

        async function openSupportChat(userId, name) {
            adminCurrentSupportUserId = userId;
            adminChatMode = 'support';

            document.getElementById('admin-chat-header').innerHTML = `
                <p class="font-bold text-gray-700">🎟️ ${name}</p>
                <p class="text-xs text-gray-400">خدمة العملاء</p>`;
            document.getElementById('admin-chat-input-bar').style.display = 'flex';

            const { data: msgs } = await sbClient.from('support_chats')
                .select('*').eq('user_id', userId).order('created_at', { ascending: true });

            const container = document.getElementById('admin-chat-messages');
            container.innerHTML = '';

            if (!msgs || msgs.length === 0) {
                container.innerHTML = '<p class="text-center text-gray-400 py-8">لا توجد رسائل بعد</p>';
                return;
            }

            msgs.forEach(m => {
                const div = document.createElement('div');
                div.style.cssText = `max-width:80%;padding:10px 14px;border-radius:12px;font-size:0.85rem;line-height:1.5;word-wrap:break-word;margin-bottom:4px;`;
                if (m.sender_role === 'admin') {
                    div.style.background = '#ede9fe';
                    div.style.alignSelf = 'flex-end';
                    div.style.marginRight = 'auto';
                    div.innerHTML = `<span style="font-size:10px;color:#6d28d9;display:block;margin-bottom:3px">🛡️ الإدارة</span>${m.message}`;
                } else {
                    div.style.background = '#fef3c7';
                    div.style.alignSelf = 'flex-start';
                    div.innerHTML = `<span style="font-size:10px;color:#92400e;display:block;margin-bottom:3px">👤 العميل</span>${m.message}`;
                }
                const t = document.createElement('span');
                t.style.cssText = 'display:block;font-size:9px;margin-top:4px;opacity:0.5;';
                t.textContent = new Date(m.created_at).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' });
                div.appendChild(t);
                container.appendChild(div);
            });
            container.scrollTop = container.scrollHeight;
        }


        // ==========================================
        // تعديل الوجهة والسعر من الشات
        // ==========================================
        async function openDestChangeModal(tripId, currentDest) {
            document.getElementById('edit-dest-input').value = currentDest || '';

            // احضار السعر الحالي من الداتابيز
            const { data: trip } = await sbClient.from('trips').select('estimated_price').eq('id', tripId).single();
            if (trip) {
                document.getElementById('edit-price-input').value = trip.estimated_price || 0;
            }
            document.getElementById('edit-dest-modal').style.display = 'flex';
        }

        async function confirmDestChange() {
            if (!adminCurrentTripId) return;
            const newDest = document.getElementById('edit-dest-input').value.trim();
            const newPrice = Number(document.getElementById('edit-price-input').value) || 0;

            if (!newDest || newPrice <= 0) {
                alert('يرجى إدخال الوجهة الجديدة والسعر بشكل صحيح');
                return;
            }

            try {
                // 1. تحديث الرحلة في الداتابيز
                const { error } = await sbClient.from('trips')
                    .update({ dropoff_location: newDest, estimated_price: newPrice })
                    .eq('id', adminCurrentTripId);

                if (error) throw error;

                // 2. إرسال رسالة في الشات بالتحديث الجديد (تظهر للكابتن بلون مميز كنظام)
                await sbClient.from('chat_messages').insert([{
                    trip_id: adminCurrentTripId,
                    sender_role: 'system',
                    sender_id: 'system',
                    sender_name: 'النظام',
                    message: `✅ تم تعديل الوجهة من قبل الإدارة.\nالوجهة الجديدة: ${newDest}\nالسعر الجديد: ${newPrice} EGP`,
                    message_type: 'system'
                }]);

                document.getElementById('edit-dest-modal').style.display = 'none';

                // تحديث الهيدر فورياً
                const routeP = document.getElementById('admin-chat-route-text');
                if (routeP) {
                    const parts = routeP.textContent.split('➝');
                    if (parts.length === 2) {
                        routeP.textContent = `${parts[0].trim()} ➝ ${newDest}`;
                    }
                }

                // تحديث جدول العمليات ضمناً (سيحدث تلقائياً إذا أعاد فتح التاب)
                alert('✅ تم تعديل الوجهة بنجاح وإشعار الكابتن');

            } catch (err) {
                console.error(err);
                alert('❌ حدث خطأ أثناء تعديل الوجهة: ' + err.message);
            }
        }

        function subscribeAdminChat(tripId) {
            if (adminChatSub) sbClient.removeChannel(adminChatSub);
            adminChatSub = sbClient.channel('chat-admin-' + tripId)
                .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'chat_messages', filter: 'trip_id=eq.' + tripId }, (payload) => {
                    appendAdminMsg(payload.new);
                }).subscribe();
        }

        async function respondDestChange(tripId, newDest, isApproved) {
            if (!confirm(`هل أنت متأكد من ${isApproved ? 'الموافقة على' : 'رفض'} الوجهة الجديدة (${newDest})؟`)) return;
            try {
                if (isApproved) {
                    await sbClient.from('trips').update({ dropoff_location: newDest }).eq('id', tripId);
                }
                const msg = isApproved ? `✅ الإدارة وافقت على تغيير الوجهة إلى: ${newDest}` : `❌ الإدارة رفضت طلب تغيير الوجهة.`;
                await sbClient.from('chat_messages').insert([{
                    trip_id: tripId, sender_role: 'admin', sender_id: 'admin', sender_name: 'الإدارة',
                    message: msg, message_type: 'system'
                }]);

                // إضافة رسالة للنظام في الشات
                appendAdminMsg({
                    trip_id: tripId, sender_role: 'system', sender_name: 'النظام',
                    message: `تم ${isApproved ? 'الموافقة على' : 'رفض'} طلب تغيير الوجهة بواسطة الإدارة.`, created_at: new Date().toISOString()
                });

                alert('✅ تم إرسال الرد للكابتن');
                if (isApproved) loadOperations();
            } catch (err) { alert('❌ خطأ: ' + err.message); }
        }

        // ==========================================
        // التقييمات
        // ==========================================
        async function loadRatings() {
            const filter = document.getElementById('ratings-filter').value;
            const list = document.getElementById('ratings-list');
            list.innerHTML = '<p class="text-center text-gray-400 py-6"><i class="fas fa-spinner fa-spin ml-2"></i>جاري التحميل...</p>';

            let query = sbClient.from('trip_ratings').select('*').order('created_at', { ascending: false });
            if (filter === 'negative') query = query.lt('driver_rating', 3);
            if (filter === 'positive') query = query.gte('driver_rating', 4);
            const { data: ratings } = await query;

            if (!ratings || ratings.length === 0) {
                list.innerHTML = '<p class="text-center text-gray-400 py-8">لا توجد تقييمات</p>';
                document.getElementById('avg-driver-rating').textContent = '--';
                document.getElementById('avg-car-rating').textContent = '--';
                document.getElementById('recommend-pct').textContent = '--';
                return;
            }

            // حساب المتوسطات
            const { data: allRatings } = await sbClient.from('trip_ratings').select('driver_rating, car_rating, service_rating, would_recommend');
            if (allRatings && allRatings.length > 0) {
                const avgD = (allRatings.reduce((s, r) => s + (r.driver_rating || 0), 0) / allRatings.length).toFixed(1);
                const avgC = (allRatings.reduce((s, r) => s + (r.car_rating || 0), 0) / allRatings.length).toFixed(1);
                const recCount = allRatings.filter(r => r.would_recommend === true).length;
                const recPct = Math.round((recCount / allRatings.length) * 100);
                document.getElementById('avg-driver-rating').textContent = avgD;
                document.getElementById('avg-car-rating').textContent = avgC;
                document.getElementById('recommend-pct').textContent = recPct + '%';
            }

            // جلب بيانات الرحلات والعملاء
            const tripIds = [...new Set(ratings.map(r => r.trip_id))];
            let tripsMap = {}, profilesMap = {};
            if (tripIds.length > 0) {
                const { data: trips } = await sbClient.from('trips').select('id, pickup_location, dropoff_location, user_id, driver_id, manual_client_name, client_phone, admin_notes').in('id', tripIds);
                if (trips) {
                    trips.forEach(t => tripsMap[t.id] = t);
                    const userIds = trips.map(t => t.user_id).filter(Boolean);
                    if (userIds.length > 0) {
                        const { data: profiles } = await sbClient.from('profiles').select('id, full_name, phone').in('id', userIds);
                        if (profiles) profiles.forEach(p => profilesMap[p.id] = p);
                    }
                    const driverIds = trips.map(t => t.driver_id).filter(Boolean);
                    if (driverIds.length > 0) {
                        const { data: drivers } = await sbClient.from('drivers').select('id, name').in('id', driverIds);
                        if (drivers) drivers.forEach(d => profilesMap['d_' + d.id] = d);
                    }
                }
            }

            list.innerHTML = ratings.map(r => {
                const trip = tripsMap[r.trip_id] || {};
                const profile = profilesMap[trip.user_id] || {};
                const driver = profilesMap['d_' + trip.driver_id] || {};
                let clientName = profile.full_name || trip.manual_client_name || 'عميل';
                let driverName = driver.name || 'كابتن';
                const isNeg = r.driver_rating < 3;
                const borderColor = isNeg ? 'border-red-400 bg-red-50' : 'border-slate-200';
                const starsHTML = (val) => '⭐'.repeat(val || 0) + '☆'.repeat(5 - (val || 0));
                const route = ((trip.pickup_location || '').split(',')[0] || '-') + ' ➝ ' + ((trip.dropoff_location || '').split(',')[0] || '-');
                const dateStr = new Date(r.created_at).toLocaleDateString('ar-EG', { year: 'numeric', month: 'short', day: 'numeric' });
                return `
                <div class="border rounded-xl p-4 ${borderColor}">
                    <div class="flex justify-between items-start mb-2">
                        <div>
                            <p class="font-bold text-sm">👤 ${clientName}</p>
                            <p class="text-[11px] text-gray-400">${route}</p>
                        </div>
                        <div class="text-left">
                            <p class="text-[10px] text-gray-400">${dateStr}</p>
                            <p class="text-[11px] text-gray-500">🚗 كابتن: ${driverName}</p>
                        </div>
                    </div>
                    <div class="grid grid-cols-3 gap-2 text-center text-xs mb-2">
                        <div><p class="text-gray-400">الكابتن</p><p>${starsHTML(r.driver_rating)}</p></div>
                        <div><p class="text-gray-400">السيارة</p><p>${starsHTML(r.car_rating)}</p></div>
                        <div><p class="text-gray-400">الخدمة</p><p>${starsHTML(r.service_rating)}</p></div>
                    </div>
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <span class="text-xs ${r.would_recommend ? 'text-green-600' : 'text-red-500'}">
                                ${r.would_recommend === true ? '👍 يرشحنا' : r.would_recommend === false ? '👎 لا يرشحنا' : '—'}
                            </span>
                            ${r.feedback_notes ? `<span class="text-xs text-gray-500">📝 ${r.feedback_notes}</span>` : ''}
                        </div>
                        ${isNeg ? `<button onclick="showPage('chat'); setTimeout(() => openAdminChatForTrip('${r.trip_id}'), 500)" class="bg-red-600 text-white text-xs px-3 py-1.5 rounded-lg font-bold hover:bg-red-700"><i class="fas fa-comment-dots ml-1"></i>تواصل مع العميل</button>` : ''}
                    </div>
                </div>`;
            }).join('');
        }

        // فتح دردشة لرحلة محددة من التقييمات
        async function openAdminChatForTrip(tripId) {
            // البحث عن المحادثة في القائمة أو فتحها مباشرة
            adminCurrentTripId = tripId;
            const { data: trip } = await sbClient.from('trips').select('pickup_location, dropoff_location, user_id, manual_client_name').eq('id', tripId).single();
            let clientName = trip?.manual_client_name || 'عميل';
            if (trip?.user_id) {
                const { data: profile } = await sbClient.from('profiles').select('full_name').eq('id', trip.user_id).single();
                if (profile) clientName = profile.full_name;
            }
            const route = ((trip?.pickup_location || '').split(',')[0]) + ' ➝ ' + ((trip?.dropoff_location || '').split(',')[0]);
            document.getElementById('admin-chat-header-name').textContent = clientName;
            document.getElementById('admin-chat-route').textContent = route;
            document.getElementById('admin-chat-input-bar').style.display = 'flex';
            await loadAdminChatMessages(tripId);
            subscribeAdminChat(tripId);
        }

        // ==========================================
        // 🎫 إدارة الكوبونات
        // ==========================================
        async function loadCouponsPage() {
            const activeEl = document.getElementById('crm-coupons-list');
            const inactiveEl = document.getElementById('crm-coupons-inactive');
            activeEl.innerHTML = '<p class="text-center text-slate-400 py-4"><i class="fas fa-spinner fa-spin ml-1"></i></p>';

            const { data: active } = await sbClient.from('coupons').select('*').eq('is_active', true).order('created_at', { ascending: false });
            const { data: inactive } = await sbClient.from('coupons').select('*').eq('is_active', false).order('created_at', { ascending: false }).limit(10);

            if (!active || active.length === 0) {
                activeEl.innerHTML = '<p class="text-center text-slate-400 py-6">لا توجد كوبونات نشطة</p>';
            } else {
                activeEl.innerHTML = active.map(c => {
                    const expired = c.expires_at && new Date(c.expires_at) < new Date();
                    const expiryLabel = c.expires_at ? new Date(c.expires_at).toLocaleDateString('ar-EG', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'لا ينتهي';
                    return `
                    <div class="flex items-center justify-between p-3 rounded-xl border ${expired ? 'bg-red-50 border-red-200 opacity-70' : 'bg-green-50 border-green-200'} gap-3">
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2">
                                <span class="font-mono font-bold text-pink-700 cursor-pointer select-all" onclick="navigator.clipboard.writeText('${c.code}'); alert('✅ تم نسخ الكود: ${c.code}')">${c.code}</span>
                                ${expired ? '<span class="text-[9px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded-full font-bold">منتهي</span>' : '<span class="text-[9px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full font-bold">نشط</span>'}
                            </div>
                            <p class="text-[10px] text-slate-500 mt-0.5">⏰ ${expiryLabel}</p>
                        </div>
                        <div class="flex items-center gap-3 shrink-0">
                            <span class="font-bold text-green-700 text-sm">${c.value} جنيه</span>
                            <button onclick="deactivateCrm('${c.id}', '${c.code}')" class="text-slate-400 hover:text-red-500 transition" title="إلغاء فوري">
                                <i class="fas fa-ban"></i>
                            </button>
                        </div>
                    </div>`;
                }).join('');
            }

            inactiveEl.innerHTML = (!inactive || inactive.length === 0)
                ? '<p class="text-center text-slate-300 py-4 text-sm">لا توجد كوبونات مُلغاة</p>'
                : inactive.map(c => `
                    <div class="flex items-center justify-between p-2 rounded-lg bg-slate-100 border border-slate-200 opacity-60 text-xs gap-2">
                        <span class="font-mono text-slate-600 line-through">${c.code}</span>
                        <span class="text-slate-500">${c.value} جنيه</span>
                        <span class="text-slate-400">${new Date(c.created_at).toLocaleDateString('ar-EG')}</span>
                    </div>`).join('');
        }

        async function createCoupon() {
            const value = document.getElementById('crm-coupon-value').value;
            const customCode = document.getElementById('crm-coupon-code').value.trim().toUpperCase();
            const expiresAt = document.getElementById('crm-coupon-expires').value;

            if (!value || parseInt(value) <= 0) return alert('❌ أدخل قيمة الخصم');
            const code = customCode || Math.random().toString(36).substring(2, 9).toUpperCase();
            const insertData = { code, value: parseInt(value), is_active: true };
            if (expiresAt) insertData.expires_at = new Date(expiresAt).toISOString();

            const { data, error } = await sbClient.from('coupons').insert([insertData]).select().single();
            if (error) {
                alert('❌ خطأ: ' + (error.message || 'تأكد من إنشاء جدول coupons في Supabase'));
                return;
            }
            alert(`✅ تم إنشاء الكوبون بنجاح!\n\nالكود: ${data.code}\nالقيمة: ${data.value} جنيه\n${expiresAt ? 'ينتهي: ' + new Date(expiresAt).toLocaleDateString('ar-EG') : 'لا ينتهي'}\n\nانقر على الكود لنسخه`);
            document.getElementById('crm-coupon-value').value = '';
            document.getElementById('crm-coupon-code').value = '';
            document.getElementById('crm-coupon-expires').value = '';
            loadCouponsPage();
        }

        async function deactivateCrm(id, code) {
            if (!confirm(`إلغاء الكوبون "${code}" فوراً؟\nلن يتمكن العملاء من استخدامه بعد الإلغاء.`)) return;
            await sbClient.from('coupons').update({ is_active: false }).eq('id', id);
            loadCouponsPage();
        }

        // ==========================================
        // إرسال بيانات الحجز إلى جوجل شيت
        // ==========================================
        const APPS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbyInsDC7MKcsfJWVwYpl5pFmiDp5XdkSF5Pi1MSJfSbKQPTp0M8F3aUhb9QHmBdbYutjA/exec';

        function sendToAdminSheet(data) {
            if (!APPS_SCRIPT_URL || APPS_SCRIPT_URL === 'PASTE_YOUR_APPS_SCRIPT_URL_HERE') return;
            fetch(APPS_SCRIPT_URL, {
                method: 'POST',
                mode: 'no-cors',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).catch(e => console.log('Sheet error:', e));
        }

    