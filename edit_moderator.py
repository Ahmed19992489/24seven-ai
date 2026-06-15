import os

file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "moderator.html"))

# Read using latin-1 to preserve exact bytes without UnicodeDecodeError
with open(file_path, "r", encoding="latin-1") as f:
    content = f.read()

# 1. HTML Replacements
old_input_html = r"""                <!-- Input Area -->
                <!-- Input Area -->
                <form id="chat-form" onsubmit="handleSend(event)" class="p-4 border-t flex items-center gap-3 bg-white">
                    <input type="text" id="chat-input" placeholder="اكتب ردك هنا..." class="input-std flex-1">
                    <button type="button" onclick="manualCoachAnalyze()" title="تحليل الرسالة (مساعد الكوتش)" class="w-10 h-10 bg-purple-100 text-purple-600 rounded-xl flex items-center justify-center hover:bg-purple-200 transition shrink-0 relative group">
                        🎓
                        <span class="absolute -top-9 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-[10px] px-2 py-1 rounded-lg opacity-0 group-hover:opacity-100 transition whitespace-nowrap">تحليل الكوتش</span>
                    </button>
                    <button type="button" onclick="suggestAiReply()" title="اقتراح رد بالذكاء الاصطناعي" class="w-10 h-10 bg-indigo-100 text-indigo-600 rounded-xl flex items-center justify-center hover:bg-indigo-200 transition shrink-0 relative group">
                        🤖
                        <span class="absolute -top-9 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-[10px] px-2 py-1 rounded-lg opacity-0 group-hover:opacity-100 transition whitespace-nowrap">اقتراح رد ذكي</span>
                    </button>
                    <button type="submit" class="w-10 h-10 bg-teal-600 text-white rounded-xl shadow-lg shadow-teal-200 flex items-center justify-center hover:scale-110 transition shrink-0">
                        <i class="fas fa-paper-plane"></i>
                    </button>
                </form>""".encode('utf-8').decode('latin-1')

new_input_html = r"""                <!-- Input Area -->
                <form id="chat-form" onsubmit="handleSend(event)" class="p-4 border-t flex items-center gap-3 bg-white relative">
                    <!-- زر اختيار صورة -->
                    <button type="button" onclick="triggerOmniImageUpload()" class="text-slate-400 hover:text-teal-600 p-2 transition shrink-0" title="إرسال صورة">
                        <i class="fas fa-image text-lg"></i>
                    </button>
                    <input type="file" id="omni-image-input" accept="image/*" class="hidden" onchange="handleOmniImageSelected(this)">

                    <!-- زر تسجيل فويس نوت -->
                    <button type="button" id="omni-record-btn" onclick="toggleOmniVoiceRecording()" class="text-slate-400 hover:text-red-500 p-2 transition shrink-0" title="تسجيل رسالة صوتية">
                        <i class="fas fa-microphone text-lg" id="omni-record-icon"></i>
                    </button>

                    <input type="text" id="chat-input" placeholder="اكتب ردك هنا..." class="input-std flex-1">
                    <button type="button" onclick="manualCoachAnalyze()" title="تحليل الرسالة (مساعد الكوتش)" class="w-10 h-10 bg-purple-100 text-purple-600 rounded-xl flex items-center justify-center hover:bg-purple-200 transition shrink-0 relative group">
                        🎓
                        <span class="absolute -top-9 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-[10px] px-2 py-1 rounded-lg opacity-0 group-hover:opacity-100 transition whitespace-nowrap">تحليل الكوتش</span>
                    </button>
                    <button type="button" onclick="suggestAiReply()" title="اقتراح رد بالذكاء الاصطناعي" class="w-10 h-10 bg-indigo-100 text-indigo-600 rounded-xl flex items-center justify-center hover:bg-indigo-200 transition shrink-0 relative group">
                        🤖
                        <span class="absolute -top-9 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-[10px] px-2 py-1 rounded-lg opacity-0 group-hover:opacity-100 transition whitespace-nowrap">اقتراح رد ذكي</span>
                    </button>
                    <button type="submit" id="omni-send-btn" class="w-10 h-10 bg-teal-600 text-white rounded-xl shadow-lg shadow-teal-200 flex items-center justify-center hover:scale-110 transition shrink-0">
                        <i class="fas fa-paper-plane"></i>
                    </button>

                    <!-- شريط حالة التسجيل الصوتي -->
                    <div id="omni-voice-recording-status" class="hidden absolute left-10 right-12 top-0 bottom-0 bg-white flex items-center justify-between px-4 rounded-full border border-red-200 z-10">
                        <span class="text-xs text-red-600 font-bold flex items-center gap-2">
                            <span class="w-2.5 h-2.5 rounded-full bg-red-600 animate-ping"></span>
                            جاري تسجيل الصوت... <span id="omni-record-timer" class="font-mono">00:00</span>
                        </span>
                        <div class="flex gap-2">
                            <button type="button" onclick="cancelOmniVoiceRecording()" class="text-slate-400 hover:text-slate-600 text-xs font-bold px-2 py-1 rounded">إلغاء</button>
                            <button type="button" onclick="stopAndSendOmniVoice()" class="bg-red-600 text-white rounded-full px-3 py-1 text-xs font-bold hover:bg-red-700">إرسال</button>
                        </div>
                    </div>
                </form>""".encode('utf-8').decode('latin-1')

# 2. JS renderMessages Replacement
old_render_messages = r"""        function renderMessages() {
            const container = document.getElementById('chat-messages');
            const chat = groupedChats[activeChatId];
            container.innerHTML = chat.messages.map(m => {
                const senderLabel = getSenderLabel(m);
                return `
                <div class="flex ${m.is_from_admin ? 'justify-end' : 'justify-start'}">
                    <div class="max-w-[75%] rounded-2xl px-4 py-2 text-sm ${m.is_from_admin ? 'bg-teal-600 text-white rounded-tr-none' : 'bg-white border text-slate-800 rounded-tl-none shadow-sm'}">
                        ${senderLabel ? `<p class="text-[10px] font-bold mb-1 opacity-80">${senderLabel}</p>` : ''}
                        <p class="whitespace-pre-wrap">${m.message_text}</p>
                        <p class="text-[9px] mt-1 opacity-70 ${m.is_from_admin ? 'text-right' : 'text-left'}">${new Date(m.created_at).toLocaleTimeString('ar-EG', {hour:'2-digit', minute:'2-digit'})}</p>
                    </div>
                </div>
            `}).join('');
            container.scrollTop = container.scrollHeight;
        }""".encode('utf-8').decode('latin-1')

new_render_messages = r"""        function escapeHtml(unsafe) {
            if (!unsafe) return '';
            return unsafe
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        function renderMessages() {
            const container = document.getElementById('chat-messages');
            const chat = groupedChats[activeChatId];
            container.innerHTML = chat.messages.map(m => {
                const senderLabel = getSenderLabel(m);
                const rawText = m.message_text || '';
                let messageHtml = '';
                
                if (rawText.startsWith('MEDIA_IMAGE:')) {
                    const parts = rawText.substring(12).split('|CAPTION:');
                    const mediaUrl = parts[0];
                    const caption = parts[1] || '';
                    messageHtml = `
                        <div class="flex flex-col gap-1">
                            <img src="${mediaUrl}" class="max-w-xs rounded-xl cursor-pointer border border-slate-200 shadow-sm transition hover:opacity-90" onclick="window.open('${mediaUrl}', '_blank')" />
                            ${caption ? `<p class="text-xs mt-1 ${m.is_from_admin ? 'text-teal-100' : 'text-slate-600'}">${escapeHtml(caption)}</p>` : ''}
                        </div>
                    `;
                } else if (rawText.startsWith('MEDIA_AUDIO:')) {
                    const mediaUrl = rawText.substring(12);
                    messageHtml = `
                        <audio src="${mediaUrl}" controls class="max-w-xs rounded-lg mt-1"></audio>
                    `;
                } else {
                    messageHtml = `<p class="whitespace-pre-wrap">${escapeHtml(rawText)}</p>`;
                }

                return `
                <div class="flex ${m.is_from_admin ? 'justify-end' : 'justify-start'}">
                    <div class="max-w-[75%] rounded-2xl px-4 py-2 text-sm ${m.is_from_admin ? 'bg-teal-600 text-white rounded-tr-none' : 'bg-white border text-slate-800 rounded-tl-none shadow-sm'}">
                        ${senderLabel ? `<p class="text-[10px] font-bold mb-1 opacity-80">${senderLabel}</p>` : ''}
                        ${messageHtml}
                        <p class="text-[9px] mt-1 opacity-70 ${m.is_from_admin ? 'text-right' : 'text-left'}">${new Date(m.created_at).toLocaleTimeString('ar-EG', {hour:'2-digit', minute:'2-digit'})}</p>
                    </div>
                </div>
            `}).join('');
            container.scrollTop = container.scrollHeight;
        }""".encode('utf-8').decode('latin-1')

# 3. JS handleSend Replacement
old_handle_send = r"""        async function handleSend(e) {
            e.preventDefault();
            const input = document.getElementById('chat-input');
            const text = input.value.trim();
            if(!text || !activeChatId) return false;
            
            if (activeChatType === 'omni') {
                const chat = groupedChats[activeChatId];
                input.value = '';
                try {
                    const apiBaseUrl = getApiBaseUrl();
                    if (!apiBaseUrl) {
                        alert('❌ تنبيه هام:\nلم يتم العثور على رابط اتصال بالسيرفر المحلي (API)!\n\nيرجى مسح هذا الكود بالموبايل أو الدخول إلى (الإعدادات ⚙️) أعلى القائمة الجانبية وإدخال رابط ngrok المتاح فى الشاشة الرئيسية للإدارة.');
                        return false;
                    }
                    const targetUrl = `${apiBaseUrl}/api/send_reply`;
                    console.log("📤 Sending to:", targetUrl);
                    
                    let apiSenderId = activeChatId;
                    let whatsappInstanceId = null;
                    if (chat.channel === 'whatsapp') {
                        if (chat.originalIds && chat.originalIds.size > 0) {
                            const originals = Array.from(chat.originalIds);
                            apiSenderId = originals.reduce((a, b) => a.length >= b.length ? a : b);
                            console.log(`📤 Resolved ${activeChatId} → ${apiSenderId} for API`);
                        }
                        if (chat.messages) {
                            for (let i = chat.messages.length - 1; i >= 0; i--) {
                                if (chat.messages[i].whatsapp_instance_id) {
                                    whatsappInstanceId = chat.messages[i].whatsapp_instance_id;
                                    break;
                                }
                            }
                        }
                    }
                    
                    const res = await fetch(targetUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'ngrok-skip-browser-warning': 'true'
                        },
                        body: JSON.stringify({ 
                            channel: chat.channel, 
                            sender_id: apiSenderId, 
                            message: text,
                            mod_name: currentModName || 'Admin',
                            whatsapp_instance_id: whatsappInstanceId
                        })
                    });
                    
                    if (res.ok) {
                        let resJson = {};
                        try { resJson = await res.json(); } catch(e) {}
                        
                        const newMsg = {
                            id: 'temp_' + Date.now(),
                            sender_id: apiSenderId,
                            sender_name: currentModName || 'Admin',
                            message_text: text,
                            is_from_admin: true,
                            created_at: new Date().toISOString(),
                            channel: chat.channel,
                            whatsapp_instance_id: whatsappInstanceId
                        };
                        chat.messages.push(newMsg);
                        allMessages.push(newMsg);
                        renderMessages();
                        loadUnifiedChats();
                        
                        // إذا كان إنستجرام في وضع التطوير - عرض تحذير بدل خطأ
                        if (resJson.status === 'warning') {
                            showToast('⚠️ إنستجرام (Dev Mode): الرسالة ظهرت في المحادثة لكن لم تُرسل للعميل. يحتاج التطبيق Advanced Access من Meta.', 'warning');
                        }
                        return true;
                    } else {
                        const errText = await res.text();
                        alert(`❌ فشل إرسال الرسالة\nالسيرفر رد بـ: ${res.status}\nالرابط: ${targetUrl}\n${errText}`);
                        return false;
                    }
                } catch(e) { 
                    console.error(e);
                    alert(`❌ خطأ في الاتصال بالسيرفر\nتأكد من فتح رابط ngrok في الموبايل أولاً.\nالرابط المستهدف: ${getApiBaseUrl()}/api/send_reply\nالخطأ: ${e.message}`);
                    return false;
                }
            } 
            else if (activeChatType === 'trip') {
                input.value = '';
                const newMsg = {
                    trip_id: activeChatId,
                    sender_role: 'admin',
                    sender_id: 'moderator',
                    sender_name: currentModName || 'المشرف',
                    message: text,
                    message_type: 'text',
                    created_at: new Date().toISOString()
                };
                
                appendUnifiedTripMsg(newMsg);
                
                try {
                    await sbClient.from('chat_messages').insert([newMsg]);
                    loadUnifiedChats();
                } catch (error) {
                    alert('فشل إرسال الرسالة: ' + error.message);
                }
            } 
            else if (activeChatType === 'support') {
                input.value = '';
                const newMsg = {
                    user_id: activeChatId,
                    sender_role: 'admin',
                    message: text,
                    created_at: new Date().toISOString()
                };
                
                appendUnifiedSupportMsg(newMsg);
                
                try {
                    await sbClient.from('support_chats').insert([{
                        user_id: activeChatId,
                        sender_role: 'admin',
                        message: text
                    }]);
                    loadUnifiedChats();
                } catch (error) {
                    alert('فشل إرسال الرسالة: ' + error.message);
                }
            }
        }""".encode('utf-8').decode('latin-1')

new_handle_send = r"""        let omniMediaRecorder = null;
        let omniAudioChunks = [];
        let omniRecordTimerInterval = null;
        let omniRecordSeconds = 0;

        function triggerOmniImageUpload() {
            document.getElementById('omni-image-input').click();
        }

        async function handleOmniImageSelected(input) {
            if (!input.files || input.files.length === 0) return;
            const file = input.files[0];
            input.value = ''; // clear
            
            if (!activeChatId) return;
            const chat = groupedChats[activeChatId];
            if (!chat) return;
            
            const caption = prompt('اكتب شرحاً للصورة (اختياري):') || '';
            
            const btn = document.getElementById('omni-send-btn');
            const origHtml = btn ? btn.innerHTML : '';
            if (btn) {
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                btn.disabled = true;
            }
            
            try {
                const formData = new FormData();
                formData.append('file', file);
                
                const apiBase = getApiBaseUrl() || '';
                const uploadRes = await fetch(`${apiBase}/api/upload`, {
                    method: 'POST',
                    body: formData
                });
                
                if (!uploadRes.ok) throw new Error('فشل رفع الصورة');
                const uploadData = await uploadRes.json();
                
                if (uploadData.status !== 'success') throw new Error(uploadData.message || 'فشل الرفع');
                
                const mediaUrl = uploadData.url;
                const messageText = `MEDIA_IMAGE:${mediaUrl}${caption ? '|CAPTION:' + caption : ''}`;
                
                await executeOmniSendReply(activeChatId, chat.channel, messageText);
                
            } catch (err) {
                alert('خطأ في إرسال الصورة: ' + err.message);
            } finally {
                if (btn) {
                    btn.innerHTML = origHtml;
                    btn.disabled = false;
                }
            }
        }

        async function toggleOmniVoiceRecording() {
            if (omniMediaRecorder && omniMediaRecorder.state === "recording") {
                stopAndSendOmniVoice();
            } else {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    omniAudioChunks = [];
                    
                    let options = { mimeType: 'audio/webm' };
                    if (!MediaRecorder.isTypeSupported('audio/webm')) {
                        options = { mimeType: 'audio/aac' };
                    }
                    if (!MediaRecorder.isTypeSupported('audio/aac')) {
                        options = {};
                    }
                    
                    omniMediaRecorder = new MediaRecorder(stream, options);
                    
                    omniMediaRecorder.ondataavailable = e => {
                        if (e.data.size > 0) {
                            omniAudioChunks.push(e.data);
                        }
                    };
                    
                    omniMediaRecorder.onstop = async () => {
                        const audioBlob = new Blob(omniAudioChunks, { type: omniMediaRecorder.mimeType || 'audio/webm' });
                        stream.getTracks().forEach(track => track.stop());
                        await uploadAndSendOmniAudio(audioBlob);
                    };
                    
                    omniMediaRecorder.start();
                    
                    document.getElementById('omni-voice-recording-status').classList.remove('hidden');
                    document.getElementById('omni-record-icon').className = "fas fa-stop text-red-600";
                    
                    omniRecordSeconds = 0;
                    document.getElementById('omni-record-timer').textContent = "00:00";
                    clearInterval(omniRecordTimerInterval);
                    omniRecordTimerInterval = setInterval(() => {
                        omniRecordSeconds++;
                        const mins = String(Math.floor(omniRecordSeconds / 60)).padStart(2, '0');
                        const secs = String(omniRecordSeconds % 60).padStart(2, '0');
                        document.getElementById('omni-record-timer').textContent = `${mins}:${secs}`;
                        
                        if (omniRecordSeconds >= 120) {
                            stopAndSendOmniVoice();
                        }
                    }, 1000);
                    
                } catch (err) {
                    alert('تعذر الوصول إلى الميكروفون: ' + err.message);
                }
            }
        }

        function cancelOmniVoiceRecording() {
            if (omniMediaRecorder && omniMediaRecorder.state === "recording") {
                omniMediaRecorder.onstop = null;
                omniMediaRecorder.stop();
                omniMediaRecorder.stream.getTracks().forEach(track => track.stop());
            }
            cleanupOmniVoiceUI();
        }

        function stopAndSendOmniVoice() {
            if (omniMediaRecorder && omniMediaRecorder.state === "recording") {
                omniMediaRecorder.stop();
            }
            cleanupOmniVoiceUI();
        }

        function cleanupOmniVoiceUI() {
            clearInterval(omniRecordTimerInterval);
            document.getElementById('omni-voice-recording-status').classList.add('hidden');
            document.getElementById('omni-record-icon').className = "fas fa-microphone text-lg";
            omniMediaRecorder = null;
        }

        async function uploadAndSendOmniAudio(blob) {
            if (!activeChatId) return;
            const chat = groupedChats[activeChatId];
            if (!chat) return;
            
            const btn = document.getElementById('omni-send-btn');
            const origHtml = btn ? btn.innerHTML : '';
            if (btn) {
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                btn.disabled = true;
            }
            
            try {
                const formData = new FormData();
                formData.append('file', blob, 'recording.webm');
                
                const apiBase = getApiBaseUrl() || '';
                const uploadRes = await fetch(`${apiBase}/api/upload`, {
                    method: 'POST',
                    body: formData
                });
                
                if (!uploadRes.ok) throw new Error('فشل رفع الملف الصوتي');
                const uploadData = await uploadRes.json();
                
                if (uploadData.status !== 'success') throw new Error(uploadData.message || 'فشل الرفع');
                
                const mediaUrl = uploadData.url;
                const messageText = `MEDIA_AUDIO:${mediaUrl}`;
                
                await executeOmniSendReply(activeChatId, chat.channel, messageText);
                
            } catch (err) {
                alert('خطأ في إرسال التسجيل الصوتي: ' + err.message);
            } finally {
                if (btn) {
                    btn.innerHTML = origHtml;
                    btn.disabled = false;
                }
            }
        }

        async function executeOmniSendReply(senderId, channel, text) {
            const apiBaseUrl = getApiBaseUrl();
            if (!apiBaseUrl) {
                throw new Error("لم يتم العثور على رابط اتصال بالسيرفر المحلي (API)!");
            }
            const targetUrl = `${apiBaseUrl}/api/send_reply`;
            const chat = groupedChats[senderId];
            
            let apiSenderId = senderId;
            let whatsappInstanceId = null;
            if (channel === 'whatsapp' && chat) {
                if (chat.originalIds && chat.originalIds.size > 0) {
                    const originals = Array.from(chat.originalIds);
                    apiSenderId = originals.reduce((a, b) => a.length >= b.length ? a : b);
                }
                if (chat.messages) {
                    for (let i = chat.messages.length - 1; i >= 0; i--) {
                        if (chat.messages[i].whatsapp_instance_id) {
                            whatsappInstanceId = chat.messages[i].whatsapp_instance_id;
                            break;
                        }
                    }
                }
            }
            
            const res = await fetch(targetUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'ngrok-skip-browser-warning': 'true'
                },
                body: JSON.stringify({ 
                    channel: channel, 
                    sender_id: apiSenderId, 
                    message: text,
                    mod_name: currentModName || 'Admin',
                    whatsapp_instance_id: whatsappInstanceId
                })
            });
            
            if (!res.ok) {
                const errorTxt = await res.text();
                throw new Error(errorTxt);
            }
            
            let resJson = {};
            try { resJson = await res.json(); } catch(e) {}

            const newMsg = {
                id: 'temp_' + Date.now(),
                sender_id: apiSenderId,
                sender_name: currentModName || 'Admin',
                message_text: text,
                is_from_admin: true,
                created_at: new Date().toISOString(),
                channel: channel,
                whatsapp_instance_id: whatsappInstanceId
            };
            if (chat) {
                chat.messages.push(newMsg);
            }
            allMessages.push(newMsg);
            renderMessages();
            loadUnifiedChats();

            if (resJson.status === 'warning') {
                showToast('⚠️ إنستجرام (Dev Mode): الرسالة ظهرت في المحادثة لكن لم تُرسل للعميل. يحتاج التطبيق Advanced Access من Meta.', 'warning');
            }
        }

        async function handleSend(e) {
            if (e) e.preventDefault();
            const input = document.getElementById('chat-input');
            const text = input.value.trim();
            if(!text || !activeChatId) return false;
            
            if (activeChatType === 'omni') {
                const chat = groupedChats[activeChatId];
                input.value = '';
                const btn = document.getElementById('omni-send-btn');
                const origHtml = btn ? btn.innerHTML : '';
                if (btn) {
                    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                    btn.disabled = true;
                }
                try {
                    await executeOmniSendReply(activeChatId, chat.channel, text);
                    return true;
                } catch(e) {
                    alert('خطأ في إرسال الرسالة: ' + e.message);
                    return false;
                } finally {
                    if (btn) {
                        btn.innerHTML = origHtml;
                        btn.disabled = false;
                    }
                    input.focus();
                }
            } 
            else if (activeChatType === 'trip') {
                input.value = '';
                const newMsg = {
                    trip_id: activeChatId,
                    sender_role: 'admin',
                    sender_id: 'moderator',
                    sender_name: currentModName || 'المشرف',
                    message: text,
                    message_type: 'text',
                    created_at: new Date().toISOString()
                };
                
                appendUnifiedTripMsg(newMsg);
                
                try {
                    await sbClient.from('chat_messages').insert([newMsg]);
                    loadUnifiedChats();
                } catch (error) {
                    alert('فشل إرسال الرسالة: ' + error.message);
                }
            } 
            else if (activeChatType === 'support') {
                input.value = '';
                const newMsg = {
                    user_id: activeChatId,
                    sender_role: 'admin',
                    message: text,
                    created_at: new Date().toISOString()
                };
                
                appendUnifiedSupportMsg(newMsg);
                
                try {
                    await sbClient.from('support_chats').insert([{
                        user_id: activeChatId,
                        sender_role: 'admin',
                        message: text
                    }]);
                    loadUnifiedChats();
                } catch (error) {
                    alert('فشل إرسال الرسالة: ' + error.message);
                }
            }
        }""".encode('utf-8').decode('latin-1')

# Clean carriage returns
old_input_html_clean = old_input_html.replace("\r\n", "\n")
new_input_html_clean = new_input_html.replace("\r\n", "\n")
old_render_messages_clean = old_render_messages.replace("\r\n", "\n")
new_render_messages_clean = new_render_messages.replace("\r\n", "\n")
old_handle_send_clean = old_handle_send.replace("\r\n", "\n")
new_handle_send_clean = new_handle_send.replace("\r\n", "\n")

content_clean = content.replace("\r\n", "\n")

# Replace input HTML
if old_input_html_clean in content_clean:
    content_clean = content_clean.replace(old_input_html_clean, new_input_html_clean)
    print("Successfully replaced chat-form HTML in moderator.html!")
else:
    print("Warning: old_input_html not found!")

# Replace renderMessages JS block
if old_render_messages_clean in content_clean:
    content_clean = content_clean.replace(old_render_messages_clean, new_render_messages_clean)
    print("Successfully replaced renderMessages JS block in moderator.html!")
else:
    print("Warning: old_render_messages not found!")

# Replace handleSend JS block
if old_handle_send_clean in content_clean:
    content_clean = content_clean.replace(old_handle_send_clean, new_handle_send_clean)
    print("Successfully replaced handleSend JS block in moderator.html!")
else:
    print("Warning: old_handle_send not found!")

# Write using latin-1 to preserve all original bytes
with open(file_path, "w", encoding="latin-1") as f:
    f.write(content_clean)

print("Done editing moderator.html!")
