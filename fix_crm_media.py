import os

# === Fix 1: Replace the OLD appendAdminUnifiedOmniMsg (line ~5838) with MEDIA-aware version ===

file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "admin-crm.html"))
with open(file_path, "r", encoding="latin-1") as f:
    content = f.read()

# The ORIGINAL function at line 5838 that needs replacement (no media support)
old_func = r"""        function appendAdminUnifiedOmniMsg(msg) {
            const area = document.getElementById('omni-messages-area');
            const timeStr = new Date(msg.created_at).toLocaleTimeString('ar-EG', {hour: '2-digit', minute:'2-digit'});
            
            const div = document.createElement('div');
            div.className = "flex w-full mb-4";
            
            if (msg.is_from_admin) {
                div.innerHTML = `
                    <div class="mr-auto max-w-[80%]">
                        <div class="bg-teal-600 text-white rounded-2xl rounded-tl-none p-3 shadow-md relative">
                            <p class="text-sm whitespace-pre-wrap">${escapeHtml(msg.message_text)}</p>
                        </div>
                        <div class="text-[10px] text-slate-400 mt-1 flex justify-end gap-1 items-center">
                            <span dir="ltr">${timeStr}</span> <i class="fas fa-check-double text-teal-500"></i>
                        </div>
                    </div>`;
            } else {
                div.innerHTML = `
                    <div class="ml-auto max-w-[80%]">
                        <div class="bg-white border border-slate-200 text-slate-800 rounded-2xl rounded-tr-none p-3 shadow-sm relative">
                            <p class="text-sm whitespace-pre-wrap">${escapeHtml(msg.message_text)}</p>
                        </div>
                        <div class="text-[10px] text-slate-400 mt-1 flex justify-start">
                            <span dir="ltr">${timeStr}</span>
                        </div>
                    </div>`;
            }
            area.appendChild(div);
        }""".encode('utf-8').decode('latin-1')

# The NEW function with MEDIA_IMAGE and MEDIA_AUDIO support
new_func = r"""        function appendAdminUnifiedOmniMsg(msg) {
            const area = document.getElementById('omni-messages-area');
            const timeStr = new Date(msg.created_at).toLocaleTimeString('ar-EG', {hour: '2-digit', minute:'2-digit'});
            
            const div = document.createElement('div');
            div.className = "flex w-full mb-4";
            
            const rawText = msg.message_text || '';
            let messageHtml = '';
            
            if (rawText.startsWith('MEDIA_IMAGE:')) {
                const parts = rawText.substring(12).split('|CAPTION:');
                const mediaUrl = parts[0];
                const caption = parts[1] || '';
                const apiBase = (typeof getStaffApiBaseUrl === 'function') ? (getStaffApiBaseUrl() || '') : '';
                const fullUrl = mediaUrl.startsWith('http') ? mediaUrl : apiBase + mediaUrl;
                
                messageHtml = `
                    <div class="flex flex-col gap-1">
                        <img src="${fullUrl}" class="max-w-xs rounded-xl cursor-pointer border border-slate-200 shadow-sm transition hover:opacity-90" onclick="window.open('${fullUrl}', '_blank')" onerror="this.onerror=null;this.src='${mediaUrl}';" />
                        ${caption ? `<p class="text-xs mt-1 ${msg.is_from_admin ? 'text-teal-100' : 'text-slate-600'}">${escapeHtml(caption)}</p>` : ''}
                    </div>
                `;
            } else if (rawText.startsWith('MEDIA_AUDIO:')) {
                const mediaUrl = rawText.substring(12);
                const apiBase = (typeof getStaffApiBaseUrl === 'function') ? (getStaffApiBaseUrl() || '') : '';
                const fullUrl = mediaUrl.startsWith('http') ? mediaUrl : apiBase + mediaUrl;
                messageHtml = `
                    <audio src="${fullUrl}" controls class="max-w-xs rounded-lg mt-1" onerror="this.src='${mediaUrl}';"></audio>
                `;
            } else {
                messageHtml = `<p class="text-sm whitespace-pre-wrap">${escapeHtml(rawText)}</p>`;
            }
            
            if (msg.is_from_admin) {
                div.innerHTML = `
                    <div class="mr-auto max-w-[80%]">
                        <div class="bg-teal-600 text-white rounded-2xl rounded-tl-none p-3 shadow-md relative">
                            ${messageHtml}
                        </div>
                        <div class="text-[10px] text-slate-400 mt-1 flex justify-end gap-1 items-center">
                            <span dir="ltr">${timeStr}</span> <i class="fas fa-check-double text-teal-500"></i>
                        </div>
                    </div>`;
            } else {
                div.innerHTML = `
                    <div class="ml-auto max-w-[80%]">
                        <div class="bg-white border border-slate-200 text-slate-800 rounded-2xl rounded-tr-none p-3 shadow-sm relative">
                            ${messageHtml}
                        </div>
                        <div class="text-[10px] text-slate-400 mt-1 flex justify-start">
                            <span dir="ltr">${timeStr}</span>
                        </div>
                    </div>`;
            }
            area.appendChild(div);
        }""".encode('utf-8').decode('latin-1')

content_clean = content.replace("\r\n", "\n")
old_func_clean = old_func.replace("\r\n", "\n")
new_func_clean = new_func.replace("\r\n", "\n")

if old_func_clean in content_clean:
    content_clean = content_clean.replace(old_func_clean, new_func_clean)
    print("[OK] Successfully replaced appendAdminUnifiedOmniMsg with MEDIA-aware version!")
else:
    print("[WARN] Could not find old appendAdminUnifiedOmniMsg to replace!")

with open(file_path, "w", encoding="latin-1") as f:
    f.write(content_clean)

print("Done fixing admin-crm.html!")
