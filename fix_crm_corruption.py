import os

file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "admin-crm.html"))
with open(file_path, "r", encoding="latin-1") as f:
    content = f.read()

# The corrupted block starts at old line ~5494 and ends at ~5547
# It contains: broken end of isLocalAdminDuplicate check + injected duplicate appendAdminUnifiedOmniMsg
# We need to fix the corrupted line and remove the duplicate function

# The corrupted text (line 5494-5495 merged):
old_corrupted = r"""                    const isLocalAdminDuplicate = msg.is_from_admin && adminAllMessages.some(m => 
                        m._adminSentLocally && m.message_text === msg.message_text && m.s        function appendAdminUnifiedOmniMsg(msg) {
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
                
                messageHtml = `
                    <div class="flex flex-col gap-1">
                        <img src="${mediaUrl}" class="max-w-xs rounded-xl cursor-pointer border border-slate-200 shadow-sm transition hover:opacity-90" onclick="window.open('${mediaUrl}', '_blank')" />
                        ${caption ? `<p class="text-xs mt-1 ${msg.is_from_admin ? 'text-teal-100' : 'text-slate-600'}">${escapeHtml(caption)}</p>` : ''}
                    </div>
                `;
            } else if (rawText.startsWith('MEDIA_AUDIO:')) {
                const mediaUrl = rawText.substring(12);
                messageHtml = `
                    <audio src="${mediaUrl}" controls class="max-w-xs rounded-lg mt-1"></audio>
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

# Fix: restore the original isLocalAdminDuplicate check properly
new_fixed = r"""                    const isLocalAdminDuplicate = msg.is_from_admin && adminAllMessages.some(m => 
                        m._adminSentLocally && m.message_text === msg.message_text && m.sender_id === msg.sender_id);""".encode('utf-8').decode('latin-1')

content_clean = content.replace("\r\n", "\n")
old_corrupted_clean = old_corrupted.replace("\r\n", "\n")
new_fixed_clean = new_fixed.replace("\r\n", "\n")

if old_corrupted_clean in content_clean:
    content_clean = content_clean.replace(old_corrupted_clean, new_fixed_clean)
    print("[OK] Successfully removed corrupted duplicate function and fixed isLocalAdminDuplicate!")
else:
    print("[WARN] Could not find the corrupted block. Trying to find partial match...")
    # Check if we can find the start of the corruption
    partial = "m._adminSentLocally && m.message_text === msg.message_text && m.s        function appendAdminUnifiedOmniMsg"
    partial_latin = partial.encode('utf-8').decode('latin-1')
    if partial_latin in content_clean:
        print("[INFO] Found partial match of corruption!")
    else:
        print("[WARN] No partial match found either. The corruption pattern may differ.")

with open(file_path, "w", encoding="latin-1") as f:
    f.write(content_clean)

print("Done fixing corrupted code in admin-crm.html!")
