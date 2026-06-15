import os

file_path = os.path.join("admin-crm.html")

# Read using latin-1 to preserve exact bytes without UnicodeDecodeError
with open(file_path, "r", encoding="latin-1") as f:
    content = f.read()

# Define the HTML and JS replacements in UTF-8, then decode to latin-1
old_input_html = """                <!-- شريط الإدخال (Input Form) -->
                <div class="p-4 bg-white border-t border-slate-200 rounded-b-xl" id="omni-input-area" style="visibility: hidden;">
                    <form onsubmit="sendOmniReply(event)" class="flex gap-2 relative">
                        <!-- متغيرات مخفية لتتبع المستقبل والقناة -->
                        <input type="hidden" id="omni-reply-sender-id">
                        <input type="hidden" id="omni-reply-channel">
                        
                        <!-- <button type="button" class="text-slate-400 hover:text-teal-600 p-2"><i class="fas fa-paperclip"></i></button> -->
                        <input type="text" id="omni-reply-text" required autocomplete="off"
                            class="flex-1 bg-slate-100 border-none rounded-full px-4 py-2 focus:outline-none focus:ring-2 focus:ring-teal-500"
                            placeholder="اكتب ردك هنا...">
                        <button type="submit" id="omni-send-btn"
                            class="bg-teal-600 hover:bg-teal-700 text-white w-10 h-10 rounded-full flex items-center justify-center shadow-lg transition transform hover:scale-105">
                            <i class="fas fa-paper-plane mr-1"></i>
                        </button>
                    </form>
                </div>""".encode('utf-8').decode('latin-1')

new_input_html = """                <!-- شريط الإدخال (Input Form) -->
                <div class="p-4 bg-white border-t border-slate-200 rounded-b-xl" id="omni-input-area" style="visibility: hidden;">
                    <form onsubmit="sendOmniReply(event)" class="flex gap-2 relative items-center">
                        <!-- متغيرات مخفية لتتبع المستقبل والقناة -->
                        <input type="hidden" id="omni-reply-sender-id">
                        <input type="hidden" id="omni-reply-channel">
                        
                        <!-- زر اختيار صورة -->
                        <button type="button" onclick="triggerOmniImageUpload()" class="text-slate-400 hover:text-teal-600 p-2 transition shrink-0" title="إرسال صورة">
                            <i class="fas fa-image text-lg"></i>
                        </button>
                        <input type="file" id="omni-image-input" accept="image/*" class="hidden" onchange="handleOmniImageSelected(this)">

                        <!-- زر تسجيل فويس نوت -->
                        <button type="button" id="omni-record-btn" onclick="toggleOmniVoiceRecording()" class="text-slate-400 hover:text-red-500 p-2 transition shrink-0" title="تسجيل رسالة صوتية">
                            <i class="fas fa-microphone text-lg" id="omni-record-icon"></i>
                        </button>
                        
                        <input type="text" id="omni-reply-text" required autocomplete="off"
                            class="flex-1 bg-slate-100 border-none rounded-full px-4 py-2 focus:outline-none focus:ring-2 focus:ring-teal-500 text-sm"
                            placeholder="اكتب ردك هنا...">
                        
                        <button type="submit" id="omni-send-btn"
                            class="bg-teal-600 hover:bg-teal-700 text-white w-10 h-10 rounded-full flex items-center justify-center shadow-lg transition transform hover:scale-105 shrink-0">
                            <i class="fas fa-paper-plane mr-1"></i>
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
                    </form>
                </div>""".encode('utf-8').decode('latin-1')

old_js_send = """        async function sendOmniReply(e) {
            if (e) e.preventDefault();
            const input = document.getElementById('omni-reply-text');
            const text = input.value.trim();
            if(!text) return;
            
            const senderId = document.getElementById('omni-reply-sender-id').value;
            const channel = document.getElementById('omni-reply-channel').value;
            
            const btn = document.getElementById('omni-send-btn');
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            btn.disabled = true;

            try {
                if (channel === 'trip') {
                    const newMsg = {
                        trip_id: senderId,
                        sender_role: 'admin',
                        sender_id: 'admin',
                        sender_name: 'الإدارة',
                        message: text,
                        message_type: 'text',
                        created_at: new Date().toISOString()
                    };
                    appendAdminUnifiedTripMsg(newMsg);
                    await sbClient.from('chat_messages').insert([newMsg]);
                    input.value = '';
                } 
                else if (channel === 'support') {
                    const newMsg = {
                        user_id: senderId,
                        sender_role: 'admin',
                        message: text,
                        created_at: new Date().toISOString()
                    };
                    appendAdminUnifiedSupportMsg(newMsg);
                    await sbClient.from('support_chats').insert([newMsg]);
                    input.value = '';
                } 
                else {
                    const apiBase = getStaffApiBaseUrl();
                    if (!apiBase) {
                        throw new Error("لم يتم العثور على رابط اتصال بالسيرفر المحلي!\\nيرجى الدخول لصفحة (الإدارة / الموظفين) وإدخال رابط ngrok المتاح فى الشاشة الرئيسية.");
                    }
                    const apiUrl = `${apiBase}/api/send_reply`;

                    const group = adminGroupedChats[senderId];
                    let whatsappInstanceId = null;
                    if (channel === 'whatsapp' && group && group.messages) {
                        for (let i = group.messages.length - 1; i >= 0; i--) {
                            if (group.messages[i].whatsapp_instance_id) {
                                whatsappInstanceId = group.messages[i].whatsapp_instance_id;
                                break;
                            }
                        }
                    }

                    const res = await fetch(apiUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'ngrok-skip-browser-warning': 'true'
                        },
                        body: JSON.stringify({
                            channel: channel,
                            sender_id: senderId,
                            message: text,
                            whatsapp_instance_id: whatsappInstanceId
                        })
                    });
                    
                    if(!res.ok) {
                        const errorTxt = await res.text();
                        throw new Error(errorTxt);
                    }

                    // نضيف الرسالة مؤقتاً فوراً للعرض السريع
                    // الـ realtime listener هيتجاهلها لأن is_from_admin ومش هيضيفها تاني
                    const tempMsg = {
                        id: 'temp_' + Date.now(),
                        channel: channel,
                        sender_id: senderId,
                        message_text: text,
                        is_from_admin: true,
                        created_at: new Date().toISOString(),
                        _adminSentLocally: true,
                        whatsapp_instance_id: whatsappInstanceId
                    };
                    
                    adminAllMessages.push(tempMsg);
                    if (group) {
                        group.messages.push(tempMsg);
                    }
                    appendAdminUnifiedOmniMsg(tempMsg);
                    scrollToOmniBottom();
                    
                    input.value = '';
                }
            } catch(e) {
                alert('خطأ في إرسال الرسالة: ' + e.message);
            } finally {
                btn.innerHTML = '<i class="fas fa-paper-plane mr-1"></i>';
                btn.disabled = false;
                input.focus();
            }
        }""".encode('utf-8').decode('latin-1')

new_js_send = """        let omniMediaRecorder = null;
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
            
            const senderId = document.getElementById('omni-reply-sender-id').value;
            const channel = document.getElementById('omni-reply-channel').value;
            if (!senderId || !channel) return;
            
            const caption = prompt('اكتب شرحاً للصورة (اختياري):') || '';
            
            const btn = document.getElementById('omni-send-btn');
            const origHtml = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            btn.disabled = true;
            
            try {
                const formData = new FormData();
                formData.append('file', file);
                
                const apiBase = getStaffApiBaseUrl() || '';
                const uploadRes = await fetch(`${apiBase}/api/upload`, {
                    method: 'POST',
                    body: formData
                });
                
                if (!uploadRes.ok) throw new Error('فشل رفع الصورة');
                const uploadData = await uploadRes.json();
                
                if (uploadData.status !== 'success') throw new Error(uploadData.message || 'فشل الرفع');
                
                const mediaUrl = uploadData.url;
                const messageText = `MEDIA_IMAGE:${mediaUrl}${caption ? '|CAPTION:' + caption : ''}`;
                
                await executeOmniSendReply(senderId, channel, messageText);
                
            } catch (err) {
                alert('خطأ في إرسال الصورة: ' + err.message);
            } finally {
                btn.innerHTML = origHtml;
                btn.disabled = false;
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
            const senderId = document.getElementById('omni-reply-sender-id').value;
            const channel = document.getElementById('omni-reply-channel').value;
            if (!senderId || !channel) return;
            
            const btn = document.getElementById('omni-send-btn');
            const origHtml = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            btn.disabled = true;
            
            try {
                const formData = new FormData();
                formData.append('file', blob, 'recording.webm');
                
                const apiBase = getStaffApiBaseUrl() || '';
                const uploadRes = await fetch(`${apiBase}/api/upload`, {
                    method: 'POST',
                    body: formData
                });
                
                if (!uploadRes.ok) throw new Error('فشل رفع الملف الصوتي');
                const uploadData = await uploadRes.json();
                
                if (uploadData.status !== 'success') throw new Error(uploadData.message || 'فشل الرفع');
                
                const mediaUrl = uploadData.url;
                const messageText = `MEDIA_AUDIO:${mediaUrl}`;
                
                await executeOmniSendReply(senderId, channel, messageText);
                
            } catch (err) {
                alert('خطأ في إرسال التسجيل الصوتي: ' + err.message);
            } finally {
                btn.innerHTML = origHtml;
                btn.disabled = false;
            }
        }

        async function executeOmniSendReply(senderId, channel, text) {
            const apiBase = getStaffApiBaseUrl();
            if (!apiBase) {
                throw new Error("لم يتم العثور على رابط اتصال بالسيرفر المحلي!\\nيرجى الدخول لصفحة (الإدارة / الموظفين) وإدخال رابط ngrok المتاح فى الشاشة الرئيسية.");
            }
            const apiUrl = `${apiBase}/api/send_reply`;

            const group = adminGroupedChats[senderId];
            let whatsappInstanceId = null;
            if (channel === 'whatsapp' && group && group.messages) {
                for (let i = group.messages.length - 1; i >= 0; i--) {
                    if (group.messages[i].whatsapp_instance_id) {
                        whatsappInstanceId = group.messages[i].whatsapp_instance_id;
                        break;
                    }
                }
            }

            const res = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'ngrok-skip-browser-warning': 'true'
                },
                body: JSON.stringify({
                    channel: channel,
                    sender_id: senderId,
                    message: text,
                    whatsapp_instance_id: whatsappInstanceId
                })
            });
            
            if(!res.ok) {
                const errorTxt = await res.text();
                throw new Error(errorTxt);
            }

            const tempMsg = {
                id: 'temp_' + Date.now(),
                channel: channel,
                sender_id: senderId,
                message_text: text,
                is_from_admin: true,
                created_at: new Date().toISOString(),
                _adminSentLocally: true,
                whatsapp_instance_id: whatsappInstanceId
            };
            
            adminAllMessages.push(tempMsg);
            if (group) {
                group.messages.push(tempMsg);
            }
            appendAdminUnifiedOmniMsg(tempMsg);
            scrollToOmniBottom();
        }

        async function sendOmniReply(e) {
            if (e) e.preventDefault();
            const input = document.getElementById('omni-reply-text');
            const text = input.value.trim();
            if(!text) return;
            
            const senderId = document.getElementById('omni-reply-sender-id').value;
            const channel = document.getElementById('omni-reply-channel').value;
            
            const btn = document.getElementById('omni-send-btn');
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            btn.disabled = true;

            try {
                if (channel === 'trip') {
                    const newMsg = {
                        trip_id: senderId,
                        sender_role: 'admin',
                        sender_id: 'admin',
                        sender_name: 'الإدارة',
                        message: text,
                        message_type: 'text',
                        created_at: new Date().toISOString()
                    };
                    appendAdminUnifiedTripMsg(newMsg);
                    await sbClient.from('chat_messages').insert([newMsg]);
                    input.value = '';
                } 
                else if (channel === 'support') {
                    const newMsg = {
                        user_id: senderId,
                        sender_role: 'admin',
                        message: text,
                        created_at: new Date().toISOString()
                    };
                    appendAdminUnifiedSupportMsg(newMsg);
                    await sbClient.from('support_chats').insert([newMsg]);
                    input.value = '';
                } 
                else {
                    await executeOmniSendReply(senderId, channel, text);
                    input.value = '';
                }
            } catch(e) {
                alert('خطأ في إرسال الرسالة: ' + e.message);
            } finally {
                btn.innerHTML = '<i class="fas fa-paper-plane mr-1"></i>';
                btn.disabled = false;
                input.focus();
            }
        }""".encode('utf-8').decode('latin-1')

# Clean carriage returns
old_js_send_clean = old_js_send.replace("\r\n", "\n")
new_js_send_clean = new_js_send.replace("\r\n", "\n")
content_clean = content.replace("\r\n", "\n")

# Replace input HTML
if old_input_html in content_clean:
    content_clean = content_clean.replace(old_input_html, new_input_html)
    print("Successfully replaced omni-input-area HTML!")
else:
    print("Warning: old_input_html not found!")

# Replace JS block
if old_js_send_clean in content_clean:
    content_clean = content_clean.replace(old_js_send_clean, new_js_send_clean)
    print("Successfully replaced sendOmniReply JS block!")
else:
    print("Warning: old_js_send not found!")

# Write using latin-1 to preserve all original bytes
with open(file_path, "w", encoding="latin-1") as f:
    f.write(content_clean)

print("Done editing admin-crm.html!")
