const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion, downloadMediaMessage } = require('@whiskeysockets/baileys');
const express = require('express');
const cors = require('cors');

const qrcode = require('qrcode');
const pino = require('pino');
const axios = require('axios');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());

const PORT = 3001;
const PYTHON_BACKEND_URL = 'http://localhost:3000';
const SUPABASE_URL = 'https://wtjwzqvmwnbvjxnmweqq.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind0and6cXZtd25idmp4bm13ZXFxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTQ2NTQwMywiZXhwIjoyMDg3MDQxNDAzfQ.WYNflQntWBCHXDnxFf2C1X1IerYZtMfMT6p6P4Dx0Vg';
const SUPABASE_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': `Bearer ${SUPABASE_KEY}`,
    'Content-Type': 'application/json'
};

// Ensure sessions directory exists
const SESSIONS_DIR = path.join(__dirname, 'sessions');
if (!fs.existsSync(SESSIONS_DIR)) {
    fs.mkdirSync(SESSIONS_DIR);
}

// Ensure uploads directory exists
const UPLOADS_DIR = path.join(__dirname, '..', 'static', 'uploads');
if (!fs.existsSync(UPLOADS_DIR)) {
    fs.mkdirSync(UPLOADS_DIR, { recursive: true });
}


// In-memory store for active sessions
// Structure: { [id]: { sock, status: 'init'|'connected'|'disconnected', qr: '', phone: '' } }
const activeSessions = {};
const groupNamesCache = {};

// Helper to update Supabase status
async function updateSupabaseInstance(id, payload) {
    try {
        await axios.patch(`${SUPABASE_URL}/rest/v1/whatsapp_instances?id=eq.${id}`, payload, {
            headers: SUPABASE_HEADERS
        });
        console.log(`[Supabase] Updated instance ${id} status:`, payload);
    } catch (err) {
        console.error(`[Supabase Error] Failed to update instance ${id}:`, err.message);
    }
}

// Initialize a session
async function initSession(id) {
    if (activeSessions[id] && activeSessions[id].status === 'connected') {
        console.log(`[Gateway] Session ${id} already connected.`);
        return activeSessions[id];
    }

    console.log(`[Gateway] Initializing session ${id}...`);
    const sessionDir = path.join(SESSIONS_DIR, `session_${id}`);
    
    // Setup state
    const { state, saveCreds } = await useMultiFileAuthState(sessionDir);
    
    // Fetch latest WhatsApp version to avoid 405 error
    let version = [2, 3000, 1023141551]; // Updated fallback WA version
    try {
        const { version: fetchedVersion, isLatest } = await fetchLatestBaileysVersion();
        version = fetchedVersion;
        console.log(`[Gateway] Session ${id} using WA Web version: ${version.join('.')}, isLatest: ${isLatest}`);
    } catch (err) {
        console.warn(`[Gateway Warning] Failed to fetch latest WhatsApp version, using fallback:`, err.message);
    }
    
    const sock = makeWASocket({
        auth: state,
        version: version,
        printQRInTerminal: false,
        logger: pino({ level: 'silent' })
    });

    activeSessions[id] = {
        sock: sock,
        status: 'init',
        qr: '',
        phone: ''
    };

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;
        
        if (qr) {
            console.log(`[Gateway] QR generated for session ${id}`);
            try {
                // Higher quality QR code for better phone scanning
                const qrBase64 = await qrcode.toDataURL(qr, {
                    scale: 8,          // bigger = easier to scan
                    margin: 2,         // small margin
                    errorCorrectionLevel: 'H', // highest error correction
                    color: {
                        dark: '#000000',
                        light: '#ffffff'
                    }
                });
                activeSessions[id].qr = qrBase64;
                activeSessions[id].qrRaw = qr; // store raw string too
                activeSessions[id].qrTimestamp = Date.now(); // track when QR was generated
                activeSessions[id].status = 'disconnected';
                // Update Supabase to disconnected if we show QR
                await updateSupabaseInstance(id, { status: 'disconnected' });
            } catch (err) {
                console.error(`[Gateway] Error converting QR to base64 for ${id}:`, err.message);
            }
        }

        if (connection === 'open') {
            const rawJid = sock.user.id;
            const phone = rawJid.split(':')[0].split('@')[0];
            console.log(`[Gateway] Session ${id} connected. Phone: ${phone}`);
            
            activeSessions[id].status = 'connected';
            activeSessions[id].phone = phone;
            activeSessions[id].qr = ''; // clear QR code
            
            // Sync with Supabase
            await updateSupabaseInstance(id, { status: 'connected', phone: phone });
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            console.log(`[Gateway] Connection closed for ${id}. Reason: ${statusCode}. Should reconnect: ${shouldReconnect}`);
            
            if (!shouldReconnect) {
                // User logged out
                cleanupSession(id);
                await updateSupabaseInstance(id, { status: 'disconnected', phone: null });
            } else {
                // Temp disconnect, try reconnecting
                activeSessions[id].status = 'disconnected';
                setTimeout(() => initSession(id), 5000);
            }
        }
    });

    // Handle incoming messages
    sock.ev.on('messages.upsert', async (m) => {
        console.log(`[Gateway Debug] messages.upsert: type=${m.type}, count=${m.messages?.length}`);
        
        if (m.type === 'notify' || m.type === 'append') {
            for (const msg of m.messages) {
                console.log(`[Gateway Debug] Processing message: fromMe=${msg.key?.fromMe}, remoteJid=${msg.key?.remoteJid}, hasMessage=${!!msg.message}`);
                
                if (msg.message) {
                    const senderJid = msg.key.remoteJid;
                    if (senderJid && (senderJid.endsWith('@s.whatsapp.net') || senderJid.endsWith('@lid') || senderJid.endsWith('@g.us'))) {
                        let resolvedJid = senderJid;
                        let senderPhone = senderJid.split('@')[0];
                        let groupName = null;
                        let isGroup = senderJid.endsWith('@g.us');
                        
                        if (isGroup) {
                            const participantJid = msg.key.participant || msg.participant;
                            if (participantJid) {
                                resolvedJid = participantJid;
                                senderPhone = participantJid.split('@')[0].split(':')[0];
                            }
                            
                            if (groupNamesCache[senderJid]) {
                                groupName = groupNamesCache[senderJid];
                            } else {
                                try {
                                    const metadata = await sock.groupMetadata(senderJid);
                                    groupName = metadata.subject || 'مجموعة واتساب';
                                    groupNamesCache[senderJid] = groupName;
                                } catch (gErr) {
                                    groupName = 'مجموعة واتساب';
                                }
                            }
                        } else if (senderJid.endsWith('@lid')) {
                            // Try metadata extraction first
                            const possiblePn = msg.senderPn || (msg.key && (msg.key.participantAlt || msg.key.remoteJidAlt));
                            if (possiblePn) {
                                resolvedJid = possiblePn;
                                senderPhone = resolvedJid.split('@')[0];
                                console.log(`[Gateway] Resolved LID ${senderJid} to phone JID ${resolvedJid} via metadata (Phone: ${senderPhone})`);
                            } else {
                                try {
                                    const [result] = await sock.onWhatsApp(senderJid);
                                    if (result && result.exists && result.jid) {
                                        resolvedJid = result.jid;
                                        senderPhone = resolvedJid.split('@')[0];
                                        console.log(`[Gateway] Resolved LID ${senderJid} to phone JID ${resolvedJid} via onWhatsApp (Phone: ${senderPhone})`);
                                    }
                                } catch (lidErr) {
                                    console.warn(`[Gateway Warning] Failed to resolve LID JID ${senderJid} via onWhatsApp:`, lidErr.message);
                                }
                            }
                        }
                        
                        const senderName = msg.pushName || senderPhone;
                        
                        // Extract message content, unwrapping ephemeral or view-once wrappers
                        let messageContent = msg.message;
                        if (messageContent.ephemeralMessage) {
                            messageContent = messageContent.ephemeralMessage.message;
                        }
                        if (messageContent.viewOnceMessage) {
                            messageContent = messageContent.viewOnceMessage.message;
                        }
                        if (messageContent.viewOnceMessageV2) {
                            messageContent = messageContent.viewOnceMessageV2.message;
                        }
                        
                        // Extract text content
                        let text = '';
                        let mediaType = null;
                        let fileExtension = '';
                        
                        if (messageContent.imageMessage) {
                            mediaType = 'image';
                            const mime = messageContent.imageMessage.mimetype || 'image/jpeg';
                            fileExtension = mime.split('/')[1] || 'jpg';
                            if (fileExtension === 'jpeg') fileExtension = 'jpg';
                        } else if (messageContent.audioMessage) {
                            mediaType = 'audio';
                            const mime = messageContent.audioMessage.mimetype || 'audio/ogg';
                            fileExtension = mime.includes('ogg') ? 'ogg' : 'mp3';
                        }
                        
                        if (mediaType) {
                            try {
                                const buffer = await downloadMediaMessage(
                                    msg,
                                    'buffer',
                                    {},
                                    {
                                        logger: pino({ level: 'silent' }),
                                        reuploadRequest: sock.updateMediaMessage
                                    }
                                );
                                if (buffer) {
                                    const fileName = `${mediaType}_${Date.now()}_${Math.floor(Math.random() * 10000)}.${fileExtension}`;
                                    
                                    // رفع الملف مباشرةً على Supabase Storage
                                    const mimeType = mediaType === 'image' ? `image/${fileExtension}` : `audio/${fileExtension}`;
                                    let publicUrl = null;
                                    try {
                                        const uploadRes = await axios.post(
                                            `${SUPABASE_URL}/storage/v1/object/omni-media/${fileName}`,
                                            buffer,
                                            {
                                                headers: {
                                                    'apikey': SUPABASE_KEY,
                                                    'Authorization': `Bearer ${SUPABASE_KEY}`,
                                                    'Content-Type': mimeType,
                                                    'x-upsert': 'true'
                                                }
                                            }
                                        );
                                        if (uploadRes.status === 200 || uploadRes.status === 201) {
                                            publicUrl = `${SUPABASE_URL}/storage/v1/object/public/omni-media/${fileName}`;
                                            console.log(`[Gateway] Uploaded media to Supabase Storage: ${publicUrl}`);
                                        }
                                    } catch (uploadErr) {
                                        console.error(`[Gateway] Supabase Storage upload failed:`, uploadErr.message);
                                        // fallback: save locally
                                        const filePath = require('path').join(UPLOADS_DIR, fileName);
                                        require('fs').writeFileSync(filePath, buffer);
                                        publicUrl = `/static/uploads/${fileName}`;
                                        console.log(`[Gateway] Fallback: saved media locally at ${filePath}`);
                                    }
                                    
                                    if (publicUrl) {
                                        if (mediaType === 'image') {
                                            const caption = messageContent.imageMessage.caption || '';
                                            text = `MEDIA_IMAGE:${publicUrl}${caption ? '|CAPTION:' + caption : ''}`;
                                        } else {
                                            text = `MEDIA_AUDIO:${publicUrl}`;
                                        }
                                    }
                                } else {
                                    try {
                                        const fs = require('fs');
                                        const logPath = require('path').join(__dirname, '..', '..', 'scratch', 'gateway_errors.log');
                                        fs.appendFileSync(logPath, `[${new Date().toISOString()}] downloadMediaMessage returned empty/null buffer. Msg key: ${JSON.stringify(msg.key)}\n`);
                                    } catch (e) {}
                                }
                            } catch (mediaErr) {
                                console.error(`[Gateway Error] Failed to download/save media:`, mediaErr.message);
                                try {
                                    const fs = require('fs');
                                    const logPath = require('path').join(__dirname, '..', '..', 'scratch', 'gateway_errors.log');
                                    fs.appendFileSync(logPath, `[${new Date().toISOString()}] downloadMediaMessage threw error: ${mediaErr.message}\nStack: ${mediaErr.stack}\nMsg: ${JSON.stringify(msg, null, 2)}\n\n`);
                                } catch (e) {}
                            }
                        }
                        
                        if (!text) {
                            if (messageContent.conversation) {
                                text = messageContent.conversation;
                            } else if (messageContent.extendedTextMessage) {
                                text = messageContent.extendedTextMessage.text;
                            } else if (messageContent.locationMessage) {
                                const lat = messageContent.locationMessage.degreesLatitude;
                                const lng = messageContent.locationMessage.degreesLongitude;
                                text = `https://maps.google.com/maps?q=${lat},${lng}`;
                            } else if (messageContent.liveLocationMessage) {
                                const lat = messageContent.liveLocationMessage.degreesLatitude;
                                const lng = messageContent.liveLocationMessage.degreesLongitude;
                                text = `https://maps.google.com/maps?q=${lat},${lng}`;
                            } else if (messageContent.imageMessage) {
                                text = messageContent.imageMessage.caption || '[صورة / Image]';
                            } else if (messageContent.videoMessage) {
                                text = messageContent.videoMessage.caption || '[فيديو / Video]';
                            } else if (messageContent.documentMessage) {
                                text = messageContent.documentMessage.caption || '[ملف / Document]';
                            } else if (messageContent.buttonsResponseMessage) {
                                text = messageContent.buttonsResponseMessage.selectedButtonId;
                            } else if (messageContent.templateButtonReplyMessage) {
                                text = messageContent.templateButtonReplyMessage.selectedId;
                            } else if (messageContent.listResponseMessage) {
                                text = messageContent.listResponseMessage.title;
                            } else {
                                console.log(`[Gateway Debug] Unhandled message types:`, Object.keys(messageContent));
                                text = '[رسالة وسائط]';
                            }
                        }
                        
                        if (!text) continue;
                        
                        if (isGroup) {
                            console.log(`[Gateway] Group msg in "${groupName}" from ${senderPhone} (Session ${id}): ${text}`);
                            try {
                                await axios.post(`${PYTHON_BACKEND_URL}/api/whatsapp/webhook/group_message`, {
                                    group_id: senderJid,
                                    group_name: groupName,
                                    sender_phone: senderPhone,
                                    sender_name: senderName,
                                    message_text: text,
                                    instance_id: id
                                });
                            } catch (err) {
                                console.error(`[Webhook Error] Failed to forward group message to Python:`, err.message);
                            }
                        } else {
                            console.log(`[Gateway] Incoming msg from ${senderPhone} (Session ${id}): ${text}`);
                            try {
                                await axios.post(`${PYTHON_BACKEND_URL}/api/whatsapp/webhook/local/${id}`, {
                                    sender_phone: senderPhone,
                                    sender_name: msg.key.fromMe ? 'Admin' : senderName,
                                    message_text: text,
                                    is_from_admin: msg.key.fromMe ? true : false
                                });
                            } catch (err) {
                                console.error(`[Webhook Error] Failed to forward message to Python:`, err.message);
                            }
                        }
                    }
                }
            }
        }
    });

    return activeSessions[id];
}

// Clean up and delete session
function cleanupSession(id) {
    console.log(`[Gateway] Cleaning up session ${id}...`);
    if (activeSessions[id]) {
        try {
            activeSessions[id].sock.ev.removeAllListeners();
            activeSessions[id].sock.logout().catch(err => {
                console.log(`[Gateway Debug] Logout promise ignored for ${id}: ${err.message}`);
            });
        } catch (e) {
            console.log(`[Gateway Debug] Error in logout call for ${id}: ${e.message}`);
        }
        delete activeSessions[id];
    }
    
    const sessionDir = path.join(SESSIONS_DIR, `session_${id}`);
    if (fs.existsSync(sessionDir)) {
        try {
            fs.rmSync(sessionDir, { recursive: true, force: true });
        } catch (e) {
            console.error(`[Gateway] Error deleting session dir: ${e.message}`);
        }
    }
}

// REST Endpoints

// Get status of an instance
app.get('/instance/:id/status', async (req, res) => {
    const { id } = req.params;
    let session = activeSessions[id];
    
    if (!session) {
        // Try to initialize it if not in memory
        session = await initSession(id);
    }
    
    return res.json({
        status: session.status,
        phone: session.phone || null
    });
});

// Get QR of an instance
app.get('/instance/:id/qr', async (req, res) => {
    const { id } = req.params;
    let session = activeSessions[id];
    
    if (!session) {
        session = await initSession(id);
    }
    
    if (session.status === 'connected') {
        return res.json({
            status: 'success',
            type: 'message',
            message: 'الحساب متصل بالفعل'
        });
    }
    
    if (session.qr) {
        return res.json({
            status: 'success',
            type: 'base64',
            qr: session.qr
        });
    }
    
    return res.json({
        status: 'error',
        message: 'رمز الـ QR غير جاهز بعد، يرجى المحاولة بعد قليل'
    });
});

// Send message via instance
app.post('/instance/:id/send', async (req, res) => {
    const { id } = req.params;
    const { to, message, media_url, media_type } = req.body;
    
    if (!to || (!message && !media_url)) {
        return res.status(400).json({ status: 'error', message: 'Missing parameters' });
    }
    
    const session = activeSessions[id];
    if (!session || session.status !== 'connected') {
        return res.status(400).json({ status: 'error', message: 'الحساب غير متصل بالواتساب' });
    }
    
    try {
        // Format destination JID: split by @ or just use number
        let phone = to.replace('+', '').replace('0020', '20').replace('@c.us', '');
        
        // Smart JID resolution: detect LID numbers vs phone numbers
        let jid;
        
        // Check if this looks like a standard phone number (starts with country code) and has less than 14 digits
        const looksLikePhone = /^(1|2[0-9]|3[0-9]|4[0-9]|5[0-9]|6[0-9]|7[0-9]|8[0-9]|9[0-9])\d{6,13}$/.test(phone) && phone.length < 14;
        
        if (looksLikePhone) {
            // Standard phone number - use @s.whatsapp.net
            jid = `${phone}@s.whatsapp.net`;
        } else {
            // Likely a LID number - try to resolve it first
            try {
                const [result] = await session.sock.onWhatsApp(`${phone}@lid`);
                if (result && result.exists && result.jid) {
                    jid = result.jid;
                    console.log(`[Gateway] Resolved LID ${phone} to JID ${jid}`);
                } else {
                    jid = `${phone}@lid`;
                    console.log(`[Gateway] Using LID JID for ${phone} (onWhatsApp lookup failed)`);
                }
            } catch (resolveErr) {
                jid = `${phone}@lid`;
                console.log(`[Gateway] Fallback to LID JID for ${phone}: ${resolveErr.message}`);
            }
        }
        
        console.log(`[Gateway] Sending to JID: ${jid}`);
        
        // إرسال ميديا عبر media_url منفصل (من الموديتور)
        let sentMsg;
        if (media_url && media_type === 'image') {
            sentMsg = await session.sock.sendMessage(jid, { image: { url: media_url }, caption: message || '' });
            console.log(`[Gateway] Image sent to ${phone} via media_url: ${media_url}`);
        } else if (media_url && media_type === 'audio') {
            sentMsg = await session.sock.sendMessage(jid, { audio: { url: media_url }, mimetype: 'audio/ogg; codecs=opus', ptt: true });
            console.log(`[Gateway] Audio sent to ${phone} via media_url: ${media_url}`);
        } else if (message && message.startsWith('MEDIA_IMAGE:')) {
            const parts = message.substring(12).split('|CAPTION:');
            const mediaUrl = parts[0];
            const caption = parts[1] || '';
            if (mediaUrl.startsWith('http')) {
                sentMsg = await session.sock.sendMessage(jid, { image: { url: mediaUrl }, caption: caption });
            } else {
                const localFilePath = path.join(__dirname, '..', mediaUrl.replace(/^\//, ''));
                if (fs.existsSync(localFilePath)) {
                    sentMsg = await session.sock.sendMessage(jid, { image: fs.readFileSync(localFilePath), caption: caption });
                } else {
                    sentMsg = await session.sock.sendMessage(jid, { image: { url: `${PYTHON_BACKEND_URL}${mediaUrl}` }, caption: caption });
                }
            }
            console.log(`[Gateway] Image sent to ${phone}: ${mediaUrl}`);
        } else if (message && message.startsWith('MEDIA_AUDIO:')) {
            const mediaUrl = message.substring(12);
            if (mediaUrl.startsWith('http')) {
                sentMsg = await session.sock.sendMessage(jid, { audio: { url: mediaUrl }, mimetype: 'audio/ogg; codecs=opus', ptt: true });
            } else {
                const localFilePath = path.join(__dirname, '..', mediaUrl.replace(/^\//, ''));
                if (fs.existsSync(localFilePath)) {
                    sentMsg = await session.sock.sendMessage(jid, { audio: fs.readFileSync(localFilePath), mimetype: 'audio/mp4', ptt: true });
                } else {
                    sentMsg = await session.sock.sendMessage(jid, { audio: { url: `${PYTHON_BACKEND_URL}${mediaUrl}` }, mimetype: 'audio/mp4', ptt: true });
                }
            }
            console.log(`[Gateway] Audio sent to ${phone}: ${mediaUrl}`);
        } else {
            sentMsg = await session.sock.sendMessage(jid, { text: message || '' });
            console.log(`[Gateway] Text sent to ${phone}: ${message}`);
        }
        
        const msgId = sentMsg?.key?.id;
        return res.json({ status: 'success', message_id: msgId });
    } catch (err) {
        console.error(`[Gateway Error] Failed to send message via ${id}:`, err.message);
        return res.status(500).json({ status: 'error', message: err.message });
    }
});


// Logout and delete instance
app.post('/instance/:id/logout', async (req, res) => {
    const { id } = req.params;
    cleanupSession(id);
    await updateSupabaseInstance(id, { status: 'disconnected', phone: null });
    return res.json({ status: 'success' });
});

// Startup hook: load all local instances from Supabase
async function loadLocalInstances() {
    console.log('[Gateway] Loading local instances from Supabase...');
    try {
        const res = await axios.get(`${SUPABASE_URL}/rest/v1/whatsapp_instances?provider=eq.local`, {
            headers: SUPABASE_HEADERS
        });
        
        if (res.status === 200 && Array.isArray(res.data)) {
            console.log(`[Gateway] Found ${res.data.length} local instances to initialize.`);
            for (const inst of res.data) {
                initSession(inst.id);
            }
        }
    } catch (err) {
        console.error('[Gateway Error] Failed to load local instances from Supabase:', err.message);
    }
}

// Start Server
app.listen(PORT, async () => {
    console.log(`[Gateway] Local WhatsApp Gateway running on http://localhost:${PORT}`);
    // Delay load to allow python backend to be up (if restarted together)
    setTimeout(loadLocalInstances, 5000);
});
