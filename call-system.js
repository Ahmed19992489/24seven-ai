/**
 * 24Seven - نظام المكالمات الداخلية
 * يستخدم WebRTC للصوت + Supabase Realtime Broadcast للإشارات
 * يخزن سجل المكالمات في call_logs لضمان الوصول حتى لو الطرف غير متصل
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
        // فحص المكالمات الفائتة بعد ثانية من التهيئة
        setTimeout(() => this._checkMissedCalls(), 1000);
    }

    // ============================================
    // 1. الاشتراك في قناة الإشارات
    // ============================================
    _subscribeToSignals() {
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
            this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        } catch (err) {
            alert('لا يمكن الوصول للميكروفون. تأكد من منح الإذن.');
            console.error('[CallSystem] getUserMedia error:', err);
            return;
        }

        this.currentCallId = `call_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        this.currentPeer = { id: toPeerId, name: toPeerName, type: toPeerType };

        // سجّل المكالمة في قاعدة البيانات كـ "جارية"
        await this._logCallToDb({
            call_id: this.currentCallId,
            caller_id: this.myId,
            caller_name: this.myName,
            caller_type: this.myType,
            callee_id: toPeerId,
            callee_name: toPeerName,
            callee_type: toPeerType,
            status: 'calling',
            started_at: new Date().toISOString()
        });

        this._createPeerConnection();

        this.localStream.getTracks().forEach(track => {
            this.pc.addTrack(track, this.localStream);
        });

        const offer = await this.pc.createOffer({ offerToReceiveAudio: true });
        await this.pc.setLocalDescription(offer);

        await this._sendSignal(toPeerId, 'call_invite', {
            sdp: offer.sdp,
            sdpType: offer.type,
            to: toPeerId,
            toName: toPeerName,
        });

        // تكرار إرسال الدعوة كل 2.5 ثانية
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

        // مهلة 30 ثانية → مكالمة فائتة
        this._callTimeout = setTimeout(async () => {
            if (!this.isCallEstablished && this.currentPeer) {
                this._showToast('لم يتم الرد من الطرف الآخر', 'warning');
                await this._updateCallLog(this.currentCallId, { status: 'missed', ended_at: new Date().toISOString() });
                this.endCall();
            }
        }, 30000);

        this._showCallingUI(toPeerName);
    }

    // ============================================
    // 5. استقبال مكالمة واردة
    // ============================================
    async _onIncomingCall(signal) {
        if (this.isCallActive) {
            if (this.currentCallId === signal.callId) return;
            await this._sendSignal(signal.from, 'call_reject', { reason: 'busy' });
            return;
        }

        if (this.currentCallId === signal.callId) {
            console.log('[CallSystem] Duplicate invite received for call:', signal.callId);
            return;
        }

        this.currentCallId = signal.callId;
        this.currentPeer = { id: signal.from, name: signal.fromName, type: signal.fromType };
        this._pendingOffer = { sdp: signal.sdp, type: signal.sdpType };

        this._playRingtone();
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

        this.localStream.getTracks().forEach(track => {
            this.pc.addTrack(track, this.localStream);
        });

        await this.pc.setRemoteDescription({
            type: this._pendingOffer.type,
            sdp: this._pendingOffer.sdp
        });

        const answer = await this.pc.createAnswer();
        await this.pc.setLocalDescription(answer);

        await this._sendSignal(this.currentPeer.id, 'call_answer', {
            sdp: answer.sdp,
            sdpType: answer.type
        });

        // تحديث سجل المكالمة
        await this._updateCallLog(this.currentCallId, { status: 'answered', answered_at: new Date().toISOString() });

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
            await this._updateCallLog(this.currentCallId, { status: 'rejected', ended_at: new Date().toISOString() });
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
        if (this.currentCallId && this.isCallEstablished) {
            await this._updateCallLog(this.currentCallId, {
                status: 'ended',
                ended_at: new Date().toISOString(),
                duration_seconds: this.callSeconds
            });
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

        this.pc.onicecandidate = async (event) => {
            if (event.candidate && this.currentPeer) {
                await this._sendSignal(this.currentPeer.id, 'ice_candidate', {
                    candidate: event.candidate.toJSON()
                });
            }
        };

        this.pc.ontrack = (event) => {
            const remoteAudio = document.getElementById('cs-remote-audio');
            if (remoteAudio) {
                remoteAudio.srcObject = event.streams[0];
                remoteAudio.play().catch(e => console.log('Audio play error:', e));
            }
        };

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

        const html = `
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

        <!-- Toast notification -->
        <div id="cs-toast" class="cs-toast" style="display:none"></div>

        <!-- إشعار المكالمة الفائتة -->
        <div id="cs-missed-banner" class="cs-missed-banner" style="display:none">
            <div class="cs-missed-icon"><i class="fas fa-phone-missed"></i></div>
            <div class="cs-missed-content">
                <span class="cs-missed-title">📵 مكالمة فائتة</span>
                <span id="cs-missed-text" class="cs-missed-sub">...</span>
            </div>
            <button onclick="document.getElementById('cs-missed-banner').style.display='none'" class="cs-missed-close">✕</button>
        </div>

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
            box-shadow: 0 0 30px rgba(251,191,36,0.4);
        }
        .cs-incoming-card .cs-avatar-ring {
            background: linear-gradient(135deg, #4ade80, #22c55e);
            box-shadow: 0 0 30px rgba(74,222,128,0.5);
        }
        .cs-avatar-icon { font-size: 36px; color: white; }

        .cs-pulse-ring {
            width: 130px; height: 130px;
            border-radius: 50%;
            border: 3px solid rgba(74,222,128,0.4);
            margin: 0 auto;
            animation: cs-pulse 1.5s infinite;
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
        .cs-active-ring { background: linear-gradient(135deg, #3b82f6, #1d4ed8) !important; box-shadow: 0 0 30px rgba(59,130,246,0.5) !important; }

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

        .cs-calling-dots { display: flex; gap: 6px; justify-content: center; margin: 16px 0 24px; }
        .cs-calling-dots span {
            width: 8px; height: 8px; border-radius: 50%;
            background: #fbbf24;
            animation: cs-bounce 1.4s infinite ease-in-out;
        }
        .cs-calling-dots span:nth-child(2) { animation-delay: 0.2s; }
        .cs-calling-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes cs-bounce { 0%,80%,100%{transform:scale(0)} 40%{transform:scale(1)} }

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

        .cs-toast {
            position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
            background: #1e293b; border: 1px solid rgba(255,255,255,0.1);
            color: white; padding: 12px 24px; border-radius: 30px;
            font-size: 14px; font-weight: 600; z-index: 100000;
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            animation: cs-fadein 0.3s ease;
        }

        /* بانر المكالمة الفائتة */
        .cs-missed-banner {
            position: fixed; bottom: 24px; left: 24px;
            background: linear-gradient(135deg, #1e293b, #0f172a);
            border: 1px solid rgba(239,68,68,0.5);
            border-radius: 16px; padding: 14px 16px;
            display: flex; align-items: center; gap: 12px;
            z-index: 99998; color: white;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(239,68,68,0.2);
            animation: cs-slidein 0.4s ease;
            max-width: 320px; min-width: 260px;
        }
        .cs-missed-icon { 
            width: 40px; height: 40px; border-radius: 50%;
            background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.3);
            display: flex; align-items: center; justify-content: center; flex-shrink: 0;
        }
        .cs-missed-icon i { color: #f87171; font-size: 16px; }
        .cs-missed-content { display: flex; flex-direction: column; gap: 2px; flex: 1; }
        .cs-missed-title { font-size: 13px; font-weight: 800; color: #f87171; }
        .cs-missed-sub { font-size: 11px; color: #94a3b8; }
        .cs-missed-close { 
            background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.2);
            color: #f87171; border-radius: 50%; width: 26px; height: 26px; cursor: pointer;
            font-size: 12px; display: flex; align-items: center; justify-content: center;
            transition: all 0.2s; flex-shrink: 0;
        }
        .cs-missed-close:hover { background: rgba(239,68,68,0.3); }
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
        const typeMap = {
            client: '👤 عميل', driver: '🚗 كابتن',
            admin: '🏢 إدارة', ops: '⚙️ تشغيل', moderator: '👮 موديتور'
        };
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
        const btn = document.getElementById('cs-speaker-btn');
        if (!btn) return;
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

    // ============================================
    // 19. نظام سجل المكالمات (Persistent Call Logs)
    // يحل مشكلة: "الكابتن مش فاتح السايت مش بتوصل الاتصال"
    // الحل: نخزن كل مكالمة في call_logs، وعند فتح الصفحة نشوف المفائتة
    // ============================================
    async _logCallToDb(callData) {
        try {
            const { error } = await this.sb.from('call_logs').upsert([callData], { onConflict: 'call_id' });
            if (error) console.log('[CallSystem] log error:', error.message);
        } catch (e) {
            console.log('[CallSystem] call_logs not available (table may not exist):', e.message);
        }
    }

    async _updateCallLog(callId, updates) {
        if (!callId) return;
        try {
            await this.sb.from('call_logs').update(updates).eq('call_id', callId);
        } catch (e) {
            console.log('[CallSystem] update call_log error:', e.message);
        }
    }

    // فحص المكالمات الفائتة عند فتح الصفحة
    async _checkMissedCalls() {
        try {
            // آخر 10 دقائق
            const tenMinAgo = new Date(Date.now() - 10 * 60 * 1000).toISOString();
            const { data: missed } = await this.sb
                .from('call_logs')
                .select('*')
                .eq('callee_id', this.myId)
                .eq('status', 'missed')
                .gte('started_at', tenMinAgo)
                .order('started_at', { ascending: false })
                .limit(5);

            if (missed && missed.length > 0) {
                const latest = missed[0];
                const typeMap = { driver: '🚗 كابتن', client: '👤 عميل', admin: '🏢 إدارة', moderator: '👮 موديتور', ops: '⚙️ تشغيل' };
                const banner = document.getElementById('cs-missed-banner');
                const text = document.getElementById('cs-missed-text');
                if (banner && text) {
                    const callerType = typeMap[latest.caller_type] || latest.caller_type;
                    const timeAgo = this._timeAgo(latest.started_at);
                    text.textContent = `${latest.caller_name} (${callerType}) - ${timeAgo}`;
                    banner.style.display = 'flex';
                    setTimeout(() => { if (banner) banner.style.display = 'none'; }, 12000);
                }
                // تحديث السجلات كـ "تمت رؤيتها"
                for (const call of missed) {
                    await this._updateCallLog(call.call_id, { status: 'seen' });
                }
            }
        } catch (e) {
            console.log('[CallSystem] missed calls check skipped (table may not exist)');
        }
    }

    _timeAgo(isoString) {
        const diff = Date.now() - new Date(isoString).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 1) return 'الآن';
        if (mins < 60) return `منذ ${mins} دقيقة`;
        return `منذ ${Math.floor(mins / 60)} ساعة`;
    }

    // جلب سجل المكالمات للعرض (للموديتور/الإدارة)
    async getCallLogs(limit = 50) {
        try {
            const { data, error } = await this.sb
                .from('call_logs')
                .select('*')
                .order('started_at', { ascending: false })
                .limit(limit);
            return error ? [] : (data || []);
        } catch (e) {
            return [];
        }
    }
}

// تصدير للاستخدام العالمي
window.CallSystem = CallSystem;
