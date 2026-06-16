/**
 * 24Seven - نظام المكالمات الداخلية
 * يستخدم WebRTC للصوت + Supabase Realtime Broadcast للإشارات
 * لا يحتاج جداول إضافية - كل شيء عبر Realtime channels
 */

class CallSystem {
    constructor(supabaseClient, myUserId, myUserName, myUserType) {
        this.sb = supabaseClient;
        this.myId = myUserId;
        this.myName = myUserName;
        this.myType = myUserType; // 'client' | 'driver' | 'admin' | 'ops' | 'moderator'

        this.pc = null;           // RTCPeerConnection
        this.localStream = null;  // ميكروفون محلي
        this.remoteStream = null; // صوت الطرف الآخر
        this.currentCallId = null;
        this.currentPeer = null;  // { id, name, type }
        this.callChannel = null;  // Supabase Realtime channel
        this.callTimer = null;
        this.callSeconds = 0;
        this.isCallActive = false;
        this.ringtone = null;
        this.isCallEstablished = false;
        this._inviteInterval = null;
        this._callTimeout = null;

        // إعداد STUN servers (مجانية من Google)
        this.rtcConfig = {
            iceServers: [
                { urls: 'stun:stun.l.google.com:19302' },
                { urls: 'stun:stun1.l.google.com:19302' },
                { urls: 'stun:stun2.l.google.com:19302' },
            ]
        };

        this._injectUI();
        this._subscribeToSignals();
    }

    // ============================================
    // 1. الاشتراك في قناة الإشارات
    // ============================================
    _subscribeToSignals() {
        // كل مستخدم يستمع على قناة خاصة به: `call:USER_ID`
        this.callChannel = this.sb
            .channel(`call:${this.myId}`, { config: { broadcast: { self: false } } })
            .on('broadcast', { event: 'signal' }, (payload) => {
                this._handleSignal(payload.payload);
            })
            .subscribe((status) => {
                console.log(`[CallSystem] Channel status for ${this.myId}:`, status);
            });
    }

    // ============================================
    // 2. إرسال إشارة للطرف الآخر
    // ============================================
    async _sendSignal(toUserId, type, data = {}) {
        const signal = {
            type,
            from: this.myId,
            fromName: this.myName,
            fromType: this.myType,
            callId: this.currentCallId,
            ...data
        };
        // نرسل على قناة المستقبل
        await this.sb.channel(`call:${toUserId}`).send({
            type: 'broadcast',
            event: 'signal',
            payload: signal
        });
        console.log(`[CallSystem] Sent signal '${type}' to ${toUserId}`);
    }

    // ============================================
    // 3. معالجة الإشارات الواردة
    // ============================================
    async _handleSignal(signal) {
        console.log('[CallSystem] Received signal:', signal.type, 'from:', signal.fromName);

        switch (signal.type) {
            case 'call_invite':
                await this._onIncomingCall(signal);
                break;
            case 'call_answer':
                await this._onCallAnswered(signal);
                break;
            case 'call_reject':
                this._onCallRejected(signal);
                break;
            case 'call_end':
                this._onCallEnded(signal);
                break;
            case 'ice_candidate':
                await this._onIceCandidate(signal);
                break;
        }
    }

    // ============================================
    // 4. بدء مكالمة جديدة
    // ============================================
    async startCall(toPeerId, toPeerName, toPeerType = 'unknown') {
        if (this.isCallActive) {
            alert('أنت في مكالمة بالفعل!');
            return;
        }

        try {
            // طلب إذن الميكروفون
            this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        } catch (err) {
            alert('لا يمكن الوصول للميكروفون. تأكد من منح الإذن.');
            console.error('[CallSystem] getUserMedia error:', err);
            return;
        }

        this.currentCallId = `call_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        this.currentPeer = { id: toPeerId, name: toPeerName, type: toPeerType };

        // إنشاء RTCPeerConnection
        this._createPeerConnection();

        // إضافة المسار الصوتي
        this.localStream.getTracks().forEach(track => {
            this.pc.addTrack(track, this.localStream);
        });

        // إنشاء offer
        const offer = await this.pc.createOffer({ offerToReceiveAudio: true });
        await this.pc.setLocalDescription(offer);

        // إرسال الدعوة أول مرة
        await this._sendSignal(toPeerId, 'call_invite', {
            sdp: offer.sdp,
            sdpType: offer.type,
            to: toPeerId,
            toName: toPeerName,
        });

        // تكرار إرسال إشارة الاتصال كل 2.5 ثانية (لضمان وصولها إذا كان المتصفح في الخلفية وتم فتحه مجدداً)
        this.isCallEstablished = false;
        this._inviteInterval = setInterval(async () => {
            if (this.currentPeer && !this.isCallEstablished) {
                console.log('[CallSystem] Re-sending call invite...');
                await this._sendSignal(toPeerId, 'call_invite', {
                    sdp: offer.sdp,
                    sdpType: offer.type,
                    to: toPeerId,
                    toName: toPeerName,
                });
            } else {
                this._stopInviteLoop();
            }
        }, 2500);

        // مهلة 30 ثانية لعدم الرد
        this._callTimeout = setTimeout(() => {
            if (!this.isCallEstablished && this.currentPeer) {
                this._showToast('لم يتم الرد من الطرف الآخر', 'warning');
                this.endCall();
            }
        }, 30000);

        // عرض واجهة "جارٍ الاتصال"
        this._showCallingUI(toPeerName);
    }

    // ============================================
    // 5. استقبال مكالمة واردة
    // ============================================
    async _onIncomingCall(signal) {
        if (this.isCallActive) {
            // لو نفس المكالمة النشطة بالفعل، تجاهلها
            if (this.currentCallId === signal.callId) {
                return;
            }
            // رفض تلقائي لو في مكالمة أخرى
            await this._sendSignal(signal.from, 'call_reject', { reason: 'busy' });
            return;
        }

        // لو نفس المكالمة التي ترن حالياً، لا تكرر تشغيل الرنة أو تحديث الواجهة
        if (this.currentCallId === signal.callId) {
            console.log('[CallSystem] Duplicate invite received for call:', signal.callId);
            return;
        }

        this.currentCallId = signal.callId;
        this.currentPeer = { id: signal.from, name: signal.fromName, type: signal.fromType };
        this._pendingOffer = { sdp: signal.sdp, type: signal.sdpType };

        // تشغيل رنة
        this._playRingtone();

        // عرض واجهة "مكالمة واردة"
        this._showIncomingUI(signal.fromName, signal.fromType);
    }

    // ============================================
    // 6. قبول المكالمة
    // ============================================
    async acceptCall() {
        if (!this.currentPeer || !this._pendingOffer) return;

        this._stopRingtone();

        try {
            this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        } catch (err) {
            alert('لا يمكن الوصول للميكروفون!');
            this._resetCall();
            return;
        }

        this._createPeerConnection();

        // إضافة الصوت المحلي
        this.localStream.getTracks().forEach(track => {
            this.pc.addTrack(track, this.localStream);
        });

        // تحديد الـ offer الواردة
        await this.pc.setRemoteDescription({
            type: this._pendingOffer.type,
            sdp: this._pendingOffer.sdp
        });

        // إنشاء answer
        const answer = await this.pc.createAnswer();
        await this.pc.setLocalDescription(answer);

        // إرسال الـ answer
        await this._sendSignal(this.currentPeer.id, 'call_answer', {
            sdp: answer.sdp,
            sdpType: answer.type
        });

        this._pendingOffer = null;
        this._showActiveCallUI(this.currentPeer.name);
    }

    // ============================================
    // 7. رفض المكالمة
    // ============================================
    async rejectCall() {
        this._stopRingtone();
        if (this.currentPeer) {
            await this._sendSignal(this.currentPeer.id, 'call_reject', { reason: 'rejected' });
        }
        this._resetCall();
        this._hideAllCallUI();
    }

    // ============================================
    // 8. إنهاء المكالمة
    // ============================================
    async endCall() {
        if (this.currentPeer) {
            await this._sendSignal(this.currentPeer.id, 'call_end', {});
        }
        this._resetCall();
        this._hideAllCallUI();
    }

    // ============================================
    // 9. معالجة استجابات الطرف الآخر
    // ============================================
    async _onCallAnswered(signal) {
        this.isCallEstablished = true;
        this._stopInviteLoop();
        if (this._callTimeout) {
            clearTimeout(this._callTimeout);
            this._callTimeout = null;
        }
        if (!this.pc) return;
        await this.pc.setRemoteDescription({
            type: signal.sdpType,
            sdp: signal.sdp
        });
        this._showActiveCallUI(this.currentPeer.name);
    }

    _onCallRejected(signal) {
        this._showToast(`${signal.fromName} رفض المكالمة`, 'warning');
        this._resetCall();
        this._hideAllCallUI();
    }

    _onCallEnded(signal) {
        this._showToast('انتهت المكالمة', 'info');
        this._resetCall();
        this._hideAllCallUI();
    }

    async _onIceCandidate(signal) {
        if (this.pc && signal.candidate) {
            try {
                await this.pc.addIceCandidate(new RTCIceCandidate(signal.candidate));
            } catch (e) {
                console.error('[CallSystem] Error adding ICE candidate:', e);
            }
        }
    }

    // ============================================
    // 10. إنشاء RTCPeerConnection
    // ============================================
    _createPeerConnection() {
        this.pc = new RTCPeerConnection(this.rtcConfig);
        this.isCallActive = true;

        // إرسال ICE candidates
        this.pc.onicecandidate = async (event) => {
            if (event.candidate && this.currentPeer) {
                await this._sendSignal(this.currentPeer.id, 'ice_candidate', {
                    candidate: event.candidate.toJSON()
                });
            }
        };

        // استقبال الصوت من الطرف الآخر
        this.pc.ontrack = (event) => {
            const remoteAudio = document.getElementById('cs-remote-audio');
            if (remoteAudio) {
                remoteAudio.srcObject = event.streams[0];
                remoteAudio.play().catch(e => console.log('Audio play error:', e));
            }
        };

        // مراقبة حالة الاتصال
        this.pc.onconnectionstatechange = () => {
            const state = this.pc?.connectionState;
            console.log('[CallSystem] Connection state:', state);
            if (state === 'connected') {
                this.isCallEstablished = true;
                this._stopInviteLoop();
                if (this._callTimeout) {
                    clearTimeout(this._callTimeout);
                    this._callTimeout = null;
                }
                this._startCallTimer();
            } else if (state === 'failed' || state === 'disconnected') {
                this._showToast('انقطع الاتصال', 'error');
                this._resetCall();
                this._hideAllCallUI();
            }
        };
    }

    // ============================================
    // 11. إعادة تعيين الحالة
    // ============================================
    _stopInviteLoop() {
        if (this._inviteInterval) {
            clearInterval(this._inviteInterval);
            this._inviteInterval = null;
        }
    }

    _resetCall() {
        this._stopCallTimer();
        this._stopRingtone();
        this._stopInviteLoop();
        if (this._callTimeout) {
            clearTimeout(this._callTimeout);
            this._callTimeout = null;
        }
        this.isCallEstablished = false;
        if (this.pc) {
            this.pc.close();
            this.pc = null;
        }
        if (this.localStream) {
            this.localStream.getTracks().forEach(t => t.stop());
            this.localStream = null;
        }
        this.isCallActive = false;
        this.currentPeer = null;
        this.currentCallId = null;
        this._pendingOffer = null;
    }

    // ============================================
    // 12. مؤقت المكالمة
    // ============================================
    _startCallTimer() {
        this.callSeconds = 0;
        this.callTimer = setInterval(() => {
            this.callSeconds++;
            const mins = String(Math.floor(this.callSeconds / 60)).padStart(2, '0');
            const secs = String(this.callSeconds % 60).padStart(2, '0');
            const el = document.getElementById('cs-timer');
            if (el) el.textContent = `${mins}:${secs}`;
        }, 1000);
    }

    _stopCallTimer() {
        if (this.callTimer) {
            clearInterval(this.callTimer);
            this.callTimer = null;
        }
        this.callSeconds = 0;
    }

    // ============================================
    // 13. رنة المكالمة
    // ============================================
    _playRingtone() {
        try {
            // نستخدم Web Audio API لإنشاء رنة بسيطة
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            let ringCount = 0;
            const maxRings = 20;

            const ring = () => {
                if (ringCount >= maxRings || !this.currentPeer) return;
                ringCount++;

                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);

                osc.frequency.setValueAtTime(440, ctx.currentTime);
                osc.frequency.setValueAtTime(480, ctx.currentTime + 0.1);
                gain.gain.setValueAtTime(0.3, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);

                osc.start(ctx.currentTime);
                osc.stop(ctx.currentTime + 0.4);

                this._ringTimeout = setTimeout(ring, 1200);
            };

            ring();
            this._audioCtx = ctx;
        } catch (e) {
            console.log('[CallSystem] Ringtone error:', e);
        }
    }

    _stopRingtone() {
        if (this._ringTimeout) {
            clearTimeout(this._ringTimeout);
            this._ringTimeout = null;
        }
        if (this._audioCtx) {
            try { this._audioCtx.close(); } catch (e) {}
            this._audioCtx = null;
        }
    }

    // ============================================
    // 14. واجهة المستخدم (UI)
    // ============================================
    _injectUI() {
        if (document.getElementById('cs-root')) return;

        const typeLabels = {
            client: '👤 عميل', driver: '🚗 كابتن',
            admin: '🏢 إدارة', ops: '⚙️ تشغيل', moderator: '👮 موديتور'
        };

        const html = `
        <!-- عنصر الصوت المخفي -->
        <audio id="cs-remote-audio" autoplay playsinline style="display:none"></audio>

        <!-- شاشة: مكالمة واردة -->
        <div id="cs-incoming" class="cs-overlay" style="display:none">
            <div class="cs-card cs-incoming-card">
                <div class="cs-pulse-ring"></div>
                <div class="cs-avatar-ring">
                    <i class="fas fa-phone-volume cs-avatar-icon"></i>
                </div>
                <p class="cs-label">📞 مكالمة واردة</p>
                <h2 class="cs-peer-name" id="cs-in-name">...</h2>
                <p class="cs-peer-type" id="cs-in-type">...</p>
                <div class="cs-actions">
                    <button class="cs-btn cs-btn-reject" onclick="window.__callSystem.rejectCall()">
                        <i class="fas fa-phone-slash"></i>
                        <span>رفض</span>
                    </button>
                    <button class="cs-btn cs-btn-accept" onclick="window.__callSystem.acceptCall()">
                        <i class="fas fa-phone"></i>
                        <span>قبول</span>
                    </button>
                </div>
            </div>
        </div>

        <!-- شاشة: جارٍ الاتصال -->
        <div id="cs-calling" class="cs-overlay" style="display:none">
            <div class="cs-card">
                <div class="cs-avatar-ring cs-calling-anim">
                    <i class="fas fa-phone cs-avatar-icon"></i>
                </div>
                <p class="cs-label">📲 جارٍ الاتصال...</p>
                <h2 class="cs-peer-name" id="cs-out-name">...</h2>
                <div class="cs-calling-dots">
                    <span></span><span></span><span></span>
                </div>
                <button class="cs-btn cs-btn-end cs-btn-wide" onclick="window.__callSystem.endCall()">
                    <i class="fas fa-phone-slash"></i>
                    <span>إلغاء</span>
                </button>
            </div>
        </div>

        <!-- شاشة: مكالمة نشطة -->
        <div id="cs-active" class="cs-overlay" style="display:none">
            <div class="cs-card">
                <div class="cs-avatar-ring cs-active-ring">
                    <i class="fas fa-phone cs-avatar-icon"></i>
                </div>
                <h2 class="cs-peer-name" id="cs-active-name">...</h2>
                <p class="cs-timer" id="cs-timer">00:00</p>
                <div class="cs-actions cs-active-actions">
                    <button class="cs-btn cs-btn-mute" id="cs-mute-btn" onclick="window.__callSystem.toggleMute()">
                        <i class="fas fa-microphone"></i>
                        <span>كتم</span>
                    </button>
                    <button class="cs-btn cs-btn-end" onclick="window.__callSystem.endCall()">
                        <i class="fas fa-phone-slash"></i>
                        <span>إنهاء</span>
                    </button>
                    <button class="cs-btn cs-btn-speaker" id="cs-speaker-btn" onclick="window.__callSystem.toggleSpeaker()">
                        <i class="fas fa-volume-up"></i>
                        <span>سماعة</span>
                    </button>
                </div>
            </div>
        </div>

        <!-- شاشة: Toast notification -->
        <div id="cs-toast" class="cs-toast" style="display:none"></div>

        <style>
        .cs-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.85);
            z-index: 99999;
            display: flex;
            align-items: center;
            justify-content: center;
            backdrop-filter: blur(8px);
            animation: cs-fadein 0.3s ease;
        }
        @keyframes cs-fadein { from { opacity:0; } to { opacity:1; } }

        .cs-card {
            background: linear-gradient(145deg, #1e293b, #0f172a);
            border: 1px solid rgba(251,191,36,0.2);
            border-radius: 28px;
            padding: 40px 32px;
            width: 320px;
            max-width: 90vw;
            text-align: center;
            box-shadow: 0 25px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.05);
            animation: cs-slidein 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        @keyframes cs-slidein {
            from { transform: scale(0.8) translateY(40px); opacity:0; }
            to { transform: scale(1) translateY(0); opacity:1; }
        }

        .cs-incoming-card { border-color: rgba(74,222,128,0.4); }

        .cs-avatar-ring {
            width: 90px; height: 90px;
            border-radius: 50%;
            background: linear-gradient(135deg, #fbbf24, #f59e0b);
            display: flex; align-items: center; justify-content: center;
            margin: 0 auto 20px;
            position: relative;
            box-shadow: 0 0 30px rgba(251,191,36,0.4);
        }
        .cs-incoming-card .cs-avatar-ring {
            background: linear-gradient(135deg, #4ade80, #22c55e);
            box-shadow: 0 0 30px rgba(74,222,128,0.5);
        }
        .cs-avatar-icon { font-size: 36px; color: white; }

        /* حلقة نبض للمكالمة الواردة */
        .cs-pulse-ring {
            position: absolute;
            width: 130px; height: 130px;
            border-radius: 50%;
            border: 3px solid rgba(74,222,128,0.4);
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            animation: cs-pulse 1.5s infinite;
            margin-top: -65px; margin-left: -65px;
            position: relative;
        }
        @keyframes cs-pulse {
            0% { transform: scale(1); opacity:0.8; }
            100% { transform: scale(1.6); opacity:0; }
        }

        .cs-calling-anim { animation: cs-ring-anim 0.8s infinite alternate; }
        @keyframes cs-ring-anim {
            from { box-shadow: 0 0 20px rgba(251,191,36,0.3); }
            to { box-shadow: 0 0 50px rgba(251,191,36,0.8); }
        }
        .cs-active-ring { background: linear-gradient(135deg, #3b82f6, #1d4ed8); box-shadow: 0 0 30px rgba(59,130,246,0.5); }

        .cs-label { color: #94a3b8; font-size: 13px; margin-bottom: 8px; }
        .cs-peer-name { color: white; font-size: 22px; font-weight: 800; margin-bottom: 6px; }
        .cs-peer-type { color: #fbbf24; font-size: 13px; margin-bottom: 24px; }
        .cs-timer { color: #4ade80; font-size: 28px; font-weight: 700; letter-spacing: 2px; margin-bottom: 28px; font-family: monospace; }

        .cs-actions { display: flex; gap: 20px; justify-content: center; }
        .cs-active-actions { gap: 14px; }

        .cs-btn {
            display: flex; flex-direction: column; align-items: center; gap: 6px;
            padding: 16px 20px;
            border-radius: 50px;
            border: none; cursor: pointer;
            font-size: 12px; font-weight: 700;
            transition: all 0.2s;
            min-width: 70px;
        }
        .cs-btn i { font-size: 22px; }
        .cs-btn:hover { transform: scale(1.08); }
        .cs-btn:active { transform: scale(0.95); }

        .cs-btn-accept { background: linear-gradient(135deg, #4ade80, #22c55e); color: white; box-shadow: 0 8px 20px rgba(74,222,128,0.4); }
        .cs-btn-reject { background: linear-gradient(135deg, #f87171, #ef4444); color: white; box-shadow: 0 8px 20px rgba(239,68,68,0.4); }
        .cs-btn-end { background: linear-gradient(135deg, #f87171, #ef4444); color: white; box-shadow: 0 8px 20px rgba(239,68,68,0.4); }
        .cs-btn-mute { background: rgba(255,255,255,0.1); color: white; border: 1px solid rgba(255,255,255,0.15); }
        .cs-btn-speaker { background: rgba(255,255,255,0.1); color: white; border: 1px solid rgba(255,255,255,0.15); }
        .cs-btn-wide { width: 80%; margin: 10px auto 0; }
        .cs-btn.active-btn { background: rgba(251,191,36,0.2); color: #fbbf24; border-color: rgba(251,191,36,0.4); }

        /* نقاط الانتظار */
        .cs-calling-dots { display: flex; gap: 6px; justify-content: center; margin: 16px 0 24px; }
        .cs-calling-dots span {
            width: 8px; height: 8px; border-radius: 50%;
            background: #fbbf24;
            animation: cs-bounce 1.4s infinite ease-in-out;
        }
        .cs-calling-dots span:nth-child(2) { animation-delay: 0.2s; }
        .cs-calling-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes cs-bounce { 0%,80%,100%{transform:scale(0)} 40%{transform:scale(1)} }

        /* زر الاتصال العائم (الذي يُضاف لكل عنصر) */
        .call-btn {
            display: inline-flex; align-items: center; gap: 5px;
            padding: 6px 12px;
            background: linear-gradient(135deg, #4ade80, #22c55e);
            color: white; border: none; border-radius: 20px;
            cursor: pointer; font-size: 12px; font-weight: 700;
            transition: all 0.2s;
            box-shadow: 0 4px 12px rgba(74,222,128,0.3);
        }
        .call-btn:hover { transform: scale(1.05); box-shadow: 0 6px 18px rgba(74,222,128,0.5); }
        .call-btn:active { transform: scale(0.95); }
        .call-btn i { font-size: 13px; }

        /* Toast */
        .cs-toast {
            position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
            background: #1e293b; border: 1px solid rgba(255,255,255,0.1);
            color: white; padding: 12px 24px; border-radius: 30px;
            font-size: 14px; font-weight: 600; z-index: 100000;
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            animation: cs-fadein 0.3s ease;
        }
        </style>
        `;

        const div = document.createElement('div');
        div.id = 'cs-root';
        div.innerHTML = html;
        document.body.appendChild(div);
    }

    // ============================================
    // 15. تحكم في الواجهة
    // ============================================
    _showIncomingUI(peerName, peerType) {
        const typeMap = { client: '👤 عميل', driver: '🚗 كابتن', admin: '🏢 إدارة', ops: '⚙️ تشغيل', moderator: '👮 موديتور' };
        document.getElementById('cs-in-name').textContent = peerName;
        document.getElementById('cs-in-type').textContent = typeMap[peerType] || peerType;
        document.getElementById('cs-incoming').style.display = 'flex';
    }

    _showCallingUI(peerName) {
        document.getElementById('cs-out-name').textContent = peerName;
        document.getElementById('cs-calling').style.display = 'flex';
    }

    _showActiveCallUI(peerName) {
        document.getElementById('cs-active-name').textContent = peerName;
        document.getElementById('cs-calling').style.display = 'none';
        document.getElementById('cs-incoming').style.display = 'none';
        document.getElementById('cs-active').style.display = 'flex';
    }

    _hideAllCallUI() {
        ['cs-incoming', 'cs-calling', 'cs-active'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });
        const timer = document.getElementById('cs-timer');
        if (timer) timer.textContent = '00:00';
    }

    // ============================================
    // 16. التحكم في الصوت
    // ============================================
    toggleMute() {
        if (!this.localStream) return;
        const audioTrack = this.localStream.getAudioTracks()[0];
        if (!audioTrack) return;
        audioTrack.enabled = !audioTrack.enabled;
        const btn = document.getElementById('cs-mute-btn');
        if (btn) {
            const isMuted = !audioTrack.enabled;
            btn.innerHTML = isMuted
                ? '<i class="fas fa-microphone-slash"></i><span>رفع الكتم</span>'
                : '<i class="fas fa-microphone"></i><span>كتم</span>';
            btn.classList.toggle('active-btn', isMuted);
        }
    }

    toggleSpeaker() {
        const audio = document.getElementById('cs-remote-audio');
        const btn = document.getElementById('cs-speaker-btn');
        if (!audio) return;
        // على الموبايل: التبديل بين السماعة الخارجية والداخلية
        const isSpeaker = btn.classList.contains('active-btn');
        btn.classList.toggle('active-btn');
        btn.innerHTML = isSpeaker
            ? '<i class="fas fa-volume-up"></i><span>سماعة</span>'
            : '<i class="fas fa-volume-mute"></i><span>هادئ</span>';
    }

    // ============================================
    // 17. دالة إنشاء زر الاتصال
    // ============================================
    createCallButton(toPeerId, toPeerName, toPeerType = 'unknown', label = '') {
        const btn = document.createElement('button');
        btn.className = 'call-btn';
        btn.innerHTML = `<i class="fas fa-phone"></i> ${label || 'اتصال'}`;
        btn.onclick = (e) => {
            e.stopPropagation();
            this.startCall(toPeerId, toPeerName, toPeerType);
        };
        return btn;
    }

    // ============================================
    // 18. Toast notifications
    // ============================================
    _showToast(message, type = 'info') {
        const toast = document.getElementById('cs-toast');
        if (!toast) return;
        const icons = { info: 'ℹ️', warning: '⚠️', error: '❌', success: '✅' };
        toast.textContent = `${icons[type] || ''} ${message}`;
        toast.style.display = 'block';
        setTimeout(() => { toast.style.display = 'none'; }, 3000);
    }
}

// تصدير للاستخدام العالمي
window.CallSystem = CallSystem;
