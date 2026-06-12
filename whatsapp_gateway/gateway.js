const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
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

// In-memory store for active sessions
// Structure: { [id]: { sock, status: 'init'|'connected'|'disconnected', qr: '', phone: '' } }
const activeSessions = {};

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
    let version = [2, 3000, 1017578701]; // Fallback WA version
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
                const qrBase64 = await qrcode.toDataURL(qr);
                activeSessions[id].qr = qrBase64;
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
        if (m.type === 'notify') {
            for (const msg of m.messages) {
                if (!msg.key.fromMe && msg.message) {
                    const senderJid = msg.key.remoteJid;
                    if (senderJid && senderJid.endsWith('@s.whatsapp.net')) {
                        const senderPhone = senderJid.split('@')[0];
                        const senderName = msg.pushName || senderPhone;
                        
                        // Extract text content
                        let text = '';
                        if (msg.message.conversation) {
                            text = msg.message.conversation;
                        } else if (msg.message.extendedTextMessage) {
                            text = msg.message.extendedTextMessage.text;
                        } else if (msg.message.imageMessage) {
                            text = '[صورة / Image]';
                        } else if (msg.message.videoMessage) {
                            text = '[فيديو / Video]';
                        } else if (msg.message.documentMessage) {
                            text = '[ملف / Document]';
                        } else if (msg.message.buttonsResponseMessage) {
                            text = msg.message.buttonsResponseMessage.selectedButtonId;
                        } else if (msg.message.templateButtonReplyMessage) {
                            text = msg.message.templateButtonReplyMessage.selectedId;
                        } else if (msg.message.listResponseMessage) {
                            text = msg.message.listResponseMessage.title;
                        } else {
                            text = '[رسالة وسائط]';
                        }

                        if (!text) continue;

                        console.log(`[Gateway] Incoming msg from ${senderPhone} (Session ${id}): ${text}`);
                        
                        // Forward to Python backend
                        try {
                            await axios.post(`${PYTHON_BACKEND_URL}/api/whatsapp/webhook/local/${id}`, {
                                sender_phone: senderPhone,
                                sender_name: senderName,
                                message_text: text
                            });
                        } catch (err) {
                            console.error(`[Webhook Error] Failed to forward message to Python:`, err.message);
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
            activeSessions[id].sock.logout();
        } catch (e) {}
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
    const { to, message } = req.body;
    
    if (!to || !message) {
        return res.status(400).json({ status: 'error', message: 'Missing parameters' });
    }
    
    const session = activeSessions[id];
    if (!session || session.status !== 'connected') {
        return res.status(400).json({ status: 'error', message: 'الحساب غير متصل بالواتساب' });
    }
    
    try {
        // Format destination JID: split by @ or just use number
        let phone = to.replace('+', '').replace('0020', '20').replace('@c.us', '');
        const jid = `${phone}@s.whatsapp.net`;
        
        await session.sock.sendMessage(jid, { text: message });
        console.log(`[Gateway] Msg sent to ${phone} via session ${id}: ${message}`);
        return res.json({ status: 'success' });
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
