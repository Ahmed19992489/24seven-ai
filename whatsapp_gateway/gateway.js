const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion, downloadMediaMessage, Browsers, isJidBroadcast, makeCacheableSignalKeyStore } = require('@whiskeysockets/baileys');
const express = require('express');
const cors = require('cors');
const NodeCache = require('node-cache');

const msgRetryCounterCache = new NodeCache();

const qrcode = require('qrcode');
const qrcodeTerminal = require('qrcode-terminal');
const pino = require('pino');
const axios = require('axios');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(cors());
app.use(express.json());

// ≡ƒ¢í∩╕Å ╪¡┘à╪º┘è╪⌐ ╪¡╪▒╪º╪│ ╪º┘ä╪│┘è╪▒┘ü╪▒ ┘à┘å ╪º┘ä╪º┘å┘ç┘è╪º╪▒ ╪╣┘å╪» ╪¡╪»┘ê╪½ ┘é╪╖╪╣ ┘ü┘è ╪º┘ä╪º╪¬╪╡╪º┘ä ╪º┘ä╪┤╪¿┘â┘è (ECONNRESET / FetchAborted)
process.on('uncaughtException', (err) => {
    console.error('[Gateway Safety] Catching uncaught exception (crash prevented):', err ? (err.message || err) : 'Unknown error');
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('[Gateway Safety] Catching unhandled rejection (crash prevented):', reason);
});

const PORT = 3001;
const PYTHON_BACKEND_URL = 'http://127.0.0.1:3000';
const SUPABASE_URL = 'https://khskudtxbypohvnreloi.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imtoc2t1ZHR4Ynlwb2h2bnJlbG9pIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NjMxMjAyOSwiZXhwIjoyMTAxODg4MDI5fQ.uyCTVGkoeoz4xB3r2muV_fLiI62QIw-65g2nVeIb62w';
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
const lidToPhoneCache = {};         // lid string → phone string
const lastOutboundRecipientBySession = {};
const msgStore = new Map();
const lidPendingMessages = new Map(); // remoteJid@lid_msgId → { instanceId, timestamp }

// Helper to update instance status in database
async function updateSupabaseInstance(id, payload) {
    try {
        await axios.post(`https://24seven-ai.com/api/db`, {
            action: 'update',
            table: 'whatsapp_instances',
            values: payload,
            filters: [{ op: 'eq', col: 'id', val: id }]
        }, { timeout: 5000 });
        console.log(`[Database] Updated instance ${id} status:`, payload);
    } catch (err) {
        // Silently catch offline/network hiccups
    }
}

// Initialize a session
async function initSession(id, forceReconnect = false) {
    if (!forceReconnect && activeSessions[id] && (activeSessions[id].status === 'connected' || activeSessions[id].status === 'initializing' || activeSessions[id].status === 'init')) {
        console.log(`[Gateway] Session ${id} already in progress or connected. (status=${activeSessions[id].status})`);
        return activeSessions[id];
    }

    // Mark as initializing immediately to block duplicate calls
    if (!activeSessions[id]) activeSessions[id] = {};
    activeSessions[id].status = 'initializing';

    console.log(`[Gateway] Initializing session ${id}...`);
    const sessionDir = path.join(SESSIONS_DIR, `session_${id}`);
    
    // Setup state
    const { state, saveCreds } = await useMultiFileAuthState(sessionDir);
    
    // Wrap state.keys to allow caching and proper LID to PN mapping
    const logger = pino({ level: 'silent' });
    const authState = {
        creds: state.creds,
        keys: makeCacheableSignalKeyStore(state.keys, logger)
    };
    
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
        auth: authState,
        version: version,
        browser: Browsers.ubuntu('Chrome'),
        printQRInTerminal: false,
        logger: pino({ level: 'silent' }),
        connectTimeoutMs: 60000,
        defaultQueryTimeoutMs: 60000,
        markOnlineOnConnect: true,
        syncFullHistory: false,
        msgRetryCounterCache,
        shouldIgnoreJid: (jid) => isJidBroadcast(jid),
        // CRITICAL: Return undefined so Baileys sends retry request to sender
        getMessage: async (key) => {
            if (key && key.remoteJid && key.id) {
                const storeKey = `${key.remoteJid}_${key.id}`;
                const stored = msgStore.get(storeKey);
                if (stored) return stored;
            }
            return undefined;
        }
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
            console.log(`\n==================================================`);
            console.log(`📲 [WhatsApp QR] يرجى مسح رمز QR التالي لربط (${id}):`);
            console.log(`==================================================\n`);
            try {
                qrcodeTerminal.generate(qr, { small: true });
            } catch (qrTermErr) {
                console.log(`[Gateway] QR String: ${qr}`);
            }
            console.log(`\n==================================================\n`);
            try {
                const qrBase64 = await qrcode.toDataURL(qr, {
                    scale: 8,
                    margin: 2,
                    errorCorrectionLevel: 'H',
                    color: { dark: '#000000', light: '#ffffff' }
                });
                activeSessions[id].qr = qrBase64;
                activeSessions[id].qrRaw = qr;
                activeSessions[id].qrTimestamp = Date.now();
                activeSessions[id].status = 'disconnected';
                await updateSupabaseInstance(id, { status: 'disconnected' });
            } catch (err) {
                console.error(`[Gateway] Error converting QR to base64 for ${id}:`, err.message);
            }
        }

        if (connection === 'open') {
            const rawJid = sock.user.id;
            const phone = rawJid.split(':')[0].split('@')[0];
            console.log(`\n==================================================`);
            console.log(`✅ [WhatsApp Gateway] تم ربط وتفعيل الحساب (${phone}) بنجاح!`);
            console.log(`🚀 النظام متصل الآن وجاهز لاستقبال وإرسال كافة الرسائل.`);
            console.log(`==================================================\n`);
            
            activeSessions[id].status = 'connected';
            activeSessions[id].phone = phone;
            activeSessions[id].qr = '';
            activeSessions[id]._retryCount = 0;
            await updateSupabaseInstance(id, { status: 'connected', phone: phone });
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            console.log(`[Gateway] Connection closed for ${id}. Reason: ${statusCode}. Should reconnect: ${shouldReconnect}`);
            
            if (!shouldReconnect) {
                cleanupSession(id);
                await updateSupabaseInstance(id, { status: 'disconnected', phone: null });
            } else {
                activeSessions[id].status = 'disconnected';
                activeSessions[id]._retryCount = (activeSessions[id]._retryCount || 0) + 1;
                const reconnectDelay = (activeSessions[id].phone) ? 5000 : Math.min(30000, 5000 * activeSessions[id]._retryCount);
                console.log(`[Gateway] Reconnecting session ${id} in ${reconnectDelay}ms (attempt #${activeSessions[id]._retryCount})...`);
                setTimeout(() => initSession(id), reconnectDelay);
            }
        }
    });

    async function processIncomingWAMessage(msg, instanceId, waSock) {
        if (!msg || !msg.key) return;
        
        // Unpack message if wrapped
        let messageContent = msg.message;
        if (!messageContent) {
            // Check msgStore if available
            const sKey = `${msg.key.remoteJid}_${msg.key.id}`;
            messageContent = msgStore.get(sKey);
        }
        if (!messageContent) return;

        const senderJid = msg.key.remoteJid;
        if (!senderJid || (!senderJid.endsWith('@s.whatsapp.net') && !senderJid.endsWith('@lid') && !senderJid.endsWith('@g.us'))) {
            return;
        }

        let resolvedJid = senderJid;
        let senderPhone = senderJid.split('@')[0].split(':')[0];
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
                    const metadata = await waSock.groupMetadata(senderJid);
                    groupName = metadata.subject || 'مجموعة واتساب';
                    groupNamesCache[senderJid] = groupName;
                } catch (gErr) {
                    groupName = 'مجموعة واتساب';
                }
            }
        } else if (senderJid.endsWith('@lid')) {
            const rawLid = senderJid.split('@')[0].split(':')[0];
            if (lidToPhoneCache[rawLid]) {
                senderPhone = lidToPhoneCache[rawLid].split(':')[0];
                resolvedJid = `${senderPhone}@s.whatsapp.net`;
            } else {
                try {
                    if (waSock.signalRepository && waSock.signalRepository.lidMapping && typeof waSock.signalRepository.lidMapping.getPNForLID === 'function') {
                        const pn = await waSock.signalRepository.lidMapping.getPNForLID(senderJid);
                        if (pn) {
                            resolvedJid = pn.includes('@') ? pn : `${pn}@s.whatsapp.net`;
                            senderPhone = resolvedJid.split('@')[0].split(':')[0];
                            lidToPhoneCache[rawLid] = senderPhone;
                        }
                    }
                } catch (sigErr) {}

                if (!senderPhone || senderPhone === rawLid) {
                    const possiblePn = msg.senderPn || (msg.key && (msg.key.participantAlt || msg.key.remoteJidAlt));
                    if (possiblePn) {
                        resolvedJid = possiblePn;
                        senderPhone = resolvedJid.split('@')[0].split(':')[0];
                        lidToPhoneCache[rawLid] = senderPhone;
                    } else {
                        const lastOut = lastOutboundRecipientBySession[instanceId];
                        if (lastOut && (Date.now() - lastOut.timestamp < 120 * 60 * 1000)) {
                            senderPhone = lastOut.phone.split(':')[0];
                            resolvedJid = `${senderPhone}@s.whatsapp.net`;
                            lidToPhoneCache[rawLid] = senderPhone;
                        }
                    }
                }
            }
        }
        
        const senderName = msg.pushName || senderPhone;
        
        // Extract message content recursively
        while (messageContent) {
            if (messageContent.ephemeralMessage) messageContent = messageContent.ephemeralMessage.message;
            else if (messageContent.viewOnceMessage) messageContent = messageContent.viewOnceMessage.message;
            else if (messageContent.viewOnceMessageV2) messageContent = messageContent.viewOnceMessageV2.message;
            else if (messageContent.viewOnceMessageV2Extension) messageContent = messageContent.viewOnceMessageV2Extension.message;
            else if (messageContent.documentWithCaptionMessage) messageContent = messageContent.documentWithCaptionMessage.message;
            else if (messageContent.editedMessage) messageContent = messageContent.editedMessage.message?.protocolMessage?.editedMessage || messageContent.editedMessage.message;
            else break;
        }

        if (!messageContent) return;

        // Skip internal protocol messages
        if (messageContent.protocolMessage || 
            messageContent.senderKeyDistributionMessage || 
            messageContent.reactionMessage || 
            messageContent.keepInChatMessage || 
            messageContent.keyExpiration ||
            messageContent.pinInChatMessage) {
            return;
        }
        
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
                        reuploadRequest: waSock.updateMediaMessage
                    }
                );
                if (buffer) {
                    const fileName = `${mediaType}_${Date.now()}_${Math.floor(Math.random() * 10000)}.${fileExtension}`;
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
                        }
                    } catch (uploadErr) {
                        const filePath = path.join(UPLOADS_DIR, fileName);
                        fs.writeFileSync(filePath, buffer);
                        publicUrl = `/static/uploads/${fileName}`;
                    }
                    
                    if (publicUrl) {
                        if (mediaType === 'image') {
                            const caption = messageContent.imageMessage.caption || '';
                            text = `MEDIA_IMAGE:${publicUrl}${caption ? '|CAPTION:' + caption : ''}`;
                        } else {
                            text = `MEDIA_AUDIO:${publicUrl}`;
                        }
                    }
                }
            } catch (mediaErr) {
                console.error(`[Gateway Error] Failed to download media:`, mediaErr.message);
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
            } else if (messageContent.audioMessage) {
                text = '[رسالة صوتية / Voice Note]';
            } else if (messageContent.documentMessage) {
                text = messageContent.documentMessage.caption || messageContent.documentMessage.fileName || '[ملف / Document]';
            } else if (messageContent.stickerMessage) {
                text = '[ملصق / Sticker]';
            } else if (messageContent.contactMessage || messageContent.contactsArrayMessage) {
                text = '[جهة اتصال / Contact]';
            } else if (messageContent.buttonsResponseMessage) {
                text = messageContent.buttonsResponseMessage.selectedButtonId;
            } else if (messageContent.templateButtonReplyMessage) {
                text = messageContent.templateButtonReplyMessage.selectedId;
            } else if (messageContent.listResponseMessage) {
                text = messageContent.listResponseMessage.title;
            } else {
                return;
            }
        }
        
        if (!text) return;
        
        if (isGroup) {
            try {
                await axios.post(`${PYTHON_BACKEND_URL}/api/whatsapp/webhook/group_message`, {
                    group_id: senderJid,
                    group_name: groupName,
                    sender_phone: senderPhone,
                    sender_name: senderName,
                    message_text: text,
                    instance_id: instanceId
                });
            } catch (err) {}
        } else {
            if (msg.key.fromMe) {
                console.log(`[Gateway Debug] SKIPPED fromMe msg to ${senderPhone} (session ${instanceId}): ${text?.substring(0,50)}`);
                try {
                    await axios.post(`https://24seven-ai.com/api/db`, {
                        action: 'insert',
                        table: 'omnichannel_messages',
                        data: {
                            channel: 'whatsapp',
                            sender_id: senderPhone,
                            sender_name: 'Admin',
                            message_text: text,
                            is_from_admin: true,
                            read_by_admin: true,
                            whatsapp_instance_id: instanceId
                        }
                    }, { timeout: 4000 });
                } catch (echoErr) {}
                return;
            }
            
            console.log(`\n📩 [Gateway Incoming] رسالة واردة من ${senderPhone} (${senderName}): "${text}"`);
            let pythonSuccess = false;
            try {
                const res = await axios.post(`${PYTHON_BACKEND_URL}/api/whatsapp/webhook/local/${instanceId}`, {
                    sender_phone: senderPhone,
                    sender_name: msg.key.fromMe ? 'Admin' : senderName,
                    message_text: text,
                    instance_id: instanceId,
                    is_from_admin: false,
                    raw_payload: msg
                }, { timeout: 15000 });
                if (res.status === 200) {
                    pythonSuccess = true;
                    console.log(`✅ [Gateway Forward] تم تمرير الرسالة بنجاح إلى معالج الذكاء الاصطناعي (Python)`);
                }
            } catch (pyErr) {
                console.error(`[Gateway Forward Error] Python server error:`, pyErr.message);
            }
            
            if (!pythonSuccess) {
                try {
                    await axios.post(`https://24seven-ai.com/api/db`, {
                        action: 'insert',
                        table: 'omnichannel_messages',
                        data: {
                            channel: 'whatsapp',
                            sender_id: senderPhone,
                            sender_name: msg.key.fromMe ? 'Admin' : senderName,
                            message_text: text,
                            is_from_admin: msg.key.fromMe ? true : false,
                            read_by_admin: msg.key.fromMe ? true : false,
                            whatsapp_instance_id: instanceId
                        }
                    }, { timeout: 4000 });
                } catch (dbErr) {}
            }
        }
    }

    // Listen for contacts.update to populate lidToPhoneCache
    sock.ev.on('contacts.update', (updates) => {
        if (!Array.isArray(updates)) return;
        for (const c of updates) {
            if (c.lid && c.id) {
                const rawLid = c.lid.split('@')[0].split(':')[0];
                const phone = c.id.split('@')[0].split(':')[0];
                if (rawLid && phone) {
                    lidToPhoneCache[rawLid] = phone;
                    console.log(`[Gateway LID] Mapped ${rawLid}@lid → ${phone}`);
                }
            }
        }
    });

    sock.ev.on('contacts.set', ({ contacts }) => {
        if (!Array.isArray(contacts)) return;
        for (const c of contacts) {
            if (c.lid && c.id) {
                const rawLid = c.lid.split('@')[0].split(':')[0];
                const phone = c.id.split('@')[0].split(':')[0];
                if (rawLid && phone) {
                    lidToPhoneCache[rawLid] = phone;
                }
            }
        }
        console.log(`[Gateway LID] contacts.set loaded ${contacts.length} contacts, cache size=${Object.keys(lidToPhoneCache).length}`);
    });

    sock.ev.on('messages.upsert', async (m) => {
    
        // Cache messages into msgStore
        if (m.messages) {
            for (const msg of m.messages) {
                if (msg.key && msg.message) {
                    const sKey = `${msg.key.remoteJid}_${msg.key.id}`;
                    msgStore.set(sKey, msg.message);
                    if (msgStore.size > 2000) {
                        const firstKey = msgStore.keys().next().value;
                        msgStore.delete(firstKey);
                    }
                }
            }
        }

        // Process incoming messages
        if (m.messages && Array.isArray(m.messages)) {
            for (const msg of m.messages) {
                const hasMsg = !!msg.message;
                const jid = msg.key?.remoteJid || '';

                if (!hasMsg && jid.endsWith('@lid') && !msg.key?.fromMe) {
                    // Mark this LID message as pending — wait for messages.update retry
                    const pendingKey = `${jid}_${msg.key?.id}`;
                    lidPendingMessages.set(pendingKey, { instanceId: id, timestamp: Date.now(), pushName: msg.pushName });
                    
                    // Clean old pending (>5 min)
                    const cutoff = Date.now() - 5 * 60 * 1000;
                    for (const [k, v] of lidPendingMessages) {
                        if (v.timestamp < cutoff) lidPendingMessages.delete(k);
                    }
                    continue;
                }

                await processIncomingWAMessage(msg, id, sock);
            }
        }
    });

    sock.ev.on('messages.update', async (updates) => {
        if (!Array.isArray(updates)) return;
        for (const update of updates) {
            if (update.update && update.update.message) {
                const pendingKey = `${update.key?.remoteJid}_${update.key?.id}`;
                const pending = lidPendingMessages.get(pendingKey);
                if (pending) lidPendingMessages.delete(pendingKey);

                const fullMsg = {
                    key: update.key,
                    message: update.update.message,
                    pushName: update.update.pushName || (pending && pending.pushName) || undefined,
                    ...update.update
                };
                await processIncomingWAMessage(fullMsg, id, sock);
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
            message: '╪º┘ä╪¡╪│╪º╪¿ ┘à╪¬╪╡┘ä ╪¿╪º┘ä┘ü╪╣┘ä'
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
        message: '╪▒┘à╪▓ ╪º┘ä┘Ç QR ╪║┘è╪▒ ╪¼╪º┘ç╪▓ ╪¿╪╣╪»╪î ┘è╪▒╪¼┘ë ╪º┘ä┘à╪¡╪º┘ê┘ä╪⌐ ╪¿╪╣╪» ┘é┘ä┘è┘ä'
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
        return res.status(400).json({ status: 'error', message: '╪º┘ä╪¡╪│╪º╪¿ ╪║┘è╪▒ ┘à╪¬╪╡┘ä ╪¿╪º┘ä┘ê╪º╪¬╪│╪º╪¿' });
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
        
        lastOutboundRecipientBySession[id] = { phone: phone.replace(/\D/g, ''), timestamp: Date.now() };
        console.log(`[Gateway] Sending to JID: ${jid}`);
        
        // ╪Ñ╪▒╪│╪º┘ä ┘à┘è╪»┘è╪º ╪╣╪¿╪▒ media_url ┘à┘å┘ü╪╡┘ä (┘à┘å ╪º┘ä┘à┘ê╪»┘è╪¬┘ê╪▒)
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
        
        // ≡ƒöä ┘à╪¡╪º┘ê┘ä╪⌐ ╪º┘ä╪¬╪¼╪»┘è╪» ╪º┘ä╪¬┘ä┘é╪º╪ª┘è ┘ä┘ä╪º╪¬╪╡╪º┘ä ┘ê╪Ñ╪╣╪º╪»╪⌐ ╪º┘ä┘à╪¡╪º┘ê┘ä╪⌐ ┘ü┘è ╪¡╪º┘ä ╪º┘å┘é╪╖╪º╪╣ ╪º┘ä╪│┘ê┘â┘è╪¬ (Connection Closed)
        if (err.message && (err.message.includes('Closed') || err.message.includes('closed') || err.message.includes('not open'))) {
            console.log(`[Gateway Auto-heal] Connection closed for session ${id}. Reconnecting socket...`);
            try {
                await initSession(id, true);
                await new Promise(r => setTimeout(r, 2500));
                const retrySession = activeSessions[id];
                if (retrySession && retrySession.sock) {
                    let retrySentMsg;
                    if (media_url && media_type === 'image') {
                        retrySentMsg = await retrySession.sock.sendMessage(jid, { image: { url: media_url }, caption: message || '' });
                    } else if (media_url && media_type === 'audio') {
                        retrySentMsg = await retrySession.sock.sendMessage(jid, { audio: { url: media_url }, mimetype: 'audio/ogg; codecs=opus', ptt: true });
                    } else {
                        retrySentMsg = await retrySession.sock.sendMessage(jid, { text: message || '' });
                    }
                    console.log(`[Gateway Auto-heal SUCCESS] Sent message after reconnect to JID: ${jid}`);
                    return res.json({ status: 'success', message_id: retrySentMsg?.key?.id });
                }
            } catch (retryErr) {
                console.error(`[Gateway Auto-heal Failed]:`, retryErr.message);
            }
        }
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

// Delete instance handler
app.delete(['/api/whatsapp/instances/:id', '/instance/:id'], async (req, res) => {
    const { id } = req.params;
    console.log(`[Gateway] Received request to delete instance ${id}`);
    cleanupSession(id);
    await updateSupabaseInstance(id, { status: 'disconnected', phone: null });
    return res.json({ status: 'success', message: 'Instance deleted' });
});


// Startup hook: load all local instances from Neon DB, or fallback to disk sessions if offline
async function loadLocalInstances() {
    console.log('[Gateway] Loading local instances...');
    const defaultInstanceId = '692921bb-a5df-451d-8527-e1ee55a736f4';
    let loadedFromCloud = false;

    try {
        const res = await axios.post(`https://24seven-ai.com/api/db`, {
            action: 'select',
            table: 'whatsapp_instances',
            select: '*',
            filters: [{ op: 'eq', col: 'provider', val: 'local' }]
        }, { timeout: 6000 });
        
        if (res.status === 200 && Array.isArray(res.data?.data) && res.data.data.length > 0) {
            console.log(`[Gateway] Found ${res.data.data.length} local instances in database.`);
            for (const inst of res.data.data) {
                const sessionDir = path.join(SESSIONS_DIR, `session_${inst.id}`);
                const credsPath = path.join(sessionDir, 'creds.json');
                const hasValidCreds = fs.existsSync(credsPath) && fs.statSync(credsPath).size > 100;

                // Start if it is the default primary instance or if it already has valid creds on disk
                if (inst.id === defaultInstanceId || hasValidCreds) {
                    console.log(`[Gateway Auto-Start] Starting instance ${inst.id} (${inst.phone || 'Primary'})...`);
                    initSession(inst.id);
                } else {
                    console.log(`[Gateway Auto-Start] Skipping unlinked secondary instance ${inst.id}.`);
                }
            }
            loadedFromCloud = true;
        }
    } catch (err) {
        console.warn(`[Gateway Notice] Cloud lookup unavailable. Switching to local session storage fallback...`);
    }

    // Always ensure the default primary service instance is running,
    // but only if it wasn't already started from the DB loop above
    if (!activeSessions[defaultInstanceId] || activeSessions[defaultInstanceId].status === undefined) {
        console.log(`[Gateway Auto-Start] Starting primary service instance ${defaultInstanceId}...`);
        initSession(defaultInstanceId);
    } else {
        console.log(`[Gateway Auto-Start] Primary instance ${defaultInstanceId} already started (status=${activeSessions[defaultInstanceId].status}), skipping duplicate start.`);
    }
}

// Start Server
app.listen(PORT, async () => {
    console.log(`[Gateway] Local WhatsApp Gateway running on http://localhost:${PORT}`);
    // Delay load to allow python backend to be up (if restarted together)
    setTimeout(loadLocalInstances, 5000);
});
