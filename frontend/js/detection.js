const BACKEND_URL = 'http://localhost:5001';
const socket = io(BACKEND_URL);

let video;
let isDetecting = false;
let frameInterval = null;
let sentence = [];
let translatedSentence = [];
let currentLanguage = 'en';
let showLandmarks = false;
let landmarkCtx = null;
let sessionTimer = null;
let sessionStartTime = null;
let totalGestures = 0;
let confidenceHistory = [];

const FRAME_RATE = 100;

const langMap = {
    'en': { code: 'en-US', name: 'English' },
    'es': { code: 'es-ES', name: 'Spanish' },
    'fr': { code: 'fr-FR', name: 'French' },
    'ar': { code: 'ar-001', name: 'Arabic' },
    'hi': { code: 'hi-IN', name: 'Hindi' },
    'ja': { code: 'ja-JP', name: 'Japanese' }
};

const HAND_CONNECTIONS = [
    [0,1],[1,2],[2,3],[3,4],
    [0,5],[5,6],[6,7],[7,8],
    [0,9],[9,10],[10,11],[11,12],
    [0,13],[13,14],[14,15],[15,16],
    [0,17],[17,18],[18,19],[19,20],
    [5,9],[9,13],[13,17]
];

const POSE_CONNECTIONS = [
    [11,12],[11,13],[13,15],[12,14],[14,16],
    [11,23],[12,24],[23,24]
];

window.onload = function() {
    const connectionStatus = document.getElementById('connectionStatus');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const clearBtn = document.getElementById('clearBtn');
    const speakEnBtn = document.getElementById('speakEnBtn');
    const speakTransBtn = document.getElementById('speakTransBtn');
    const translateBtn = document.getElementById('translateBtn');
    const sentenceDisplay = document.getElementById('sentenceDisplay');
    const translatedDisplay = document.getElementById('translatedDisplay');
    const languageSelect = document.getElementById('languageSelect');
    const landmarkToggle = document.getElementById('landmarkToggle');
    const landmarkCanvas = document.getElementById('landmarkCanvas');
    const consentModal = document.getElementById('consentModal');
    const consentAccept = document.getElementById('consentAccept');
    const consentDecline = document.getElementById('consentDecline');

    landmarkCtx = landmarkCanvas.getContext('2d');
    stopBtn.disabled = true;
    window.speechSynthesis.getVoices();

    socket.on('connect', () => {
        connectionStatus.className = 'connection-status connected';
        connectionStatus.innerHTML = '🟢 Connected to Sign Language API';
    });

    socket.on('disconnect', () => {
        connectionStatus.className = 'connection-status disconnected';
        connectionStatus.innerHTML = '🔴 Disconnected from server';
        stopDetection();
    });

    socket.on('prediction', (data) => {
        updateConfidenceBars(data);

        if (data.hand_detected) {
            statusDot.className = 'status-dot active';
            statusText.textContent = 'LIVE';
            const pd = document.getElementById('presStatusDot');
            const pt = document.getElementById('presStatusText');
            if (pd) { pd.style.background = '#00ff88'; pd.style.animation = 'pulse 1.5s infinite'; }
            if (pt) { pt.style.color = '#00ff88'; pt.textContent = 'LIVE'; }
        } else {
            statusDot.className = 'status-dot';
            statusText.textContent = 'No Hands';
            const pd2 = document.getElementById('presStatusDot');
            const pt2 = document.getElementById('presStatusText');
            if (pd2) { pd2.style.background = '#ffaa00'; pd2.style.animation = 'none'; }
            if (pt2) { pt2.style.color = '#ffaa00'; pt2.textContent = 'No Hands'; }
        }

        if (showLandmarks && data.landmarks) {
            drawLandmarks(data.landmarks);
        } else if (!showLandmarks) {
            landmarkCtx.clearRect(0, 0, landmarkCanvas.width, landmarkCanvas.height);
        }

        if (data.gesture && data.gesture !== '') {
            if (sentence.length === 0 || sentence[sentence.length - 1] !== data.gesture) {
                sentence.push(data.gesture);
                if (sentence.length > 5) sentence.shift();
                updateSentenceDisplay();
                translatedSentence = [];
                updateTranslatedDisplay();

                totalGestures++;
                document.getElementById('totalGestures').textContent = totalGestures;

                if (data.confidence) {
                    confidenceHistory.push(data.confidence);
                    const avg = confidenceHistory.reduce((a,b) => a+b, 0) / confidenceHistory.length;
                    document.getElementById('avgConfidence').textContent = (avg*100).toFixed(0) + '%';
                }

                if (localStorage.getItem('signbridge_consent') === 'true') {
                    saveContribution(data.gesture, data.confidence);
                }
            }
        }
    });

    socket.on('error', (data) => { console.error('Server error:', data.message); });

    function drawLandmarks(landmarks) {
        const videoEl = document.getElementById('videoElement');
        landmarkCanvas.width = videoEl.videoWidth || 640;
        landmarkCanvas.height = videoEl.videoHeight || 480;
        landmarkCtx.clearRect(0, 0, landmarkCanvas.width, landmarkCanvas.height);

        const w = landmarkCanvas.width;
        const h = landmarkCanvas.height;

        // Mirror x coordinate to match mirrored video display
        function mx(x) { return (1 - x) * w; }
        function my(y) { return y * h; }

        function drawPoints(points, color, radius) {
            points.forEach(p => {
                landmarkCtx.beginPath();
                landmarkCtx.arc(mx(p.x), my(p.y), radius, 0, 2 * Math.PI);
                landmarkCtx.fillStyle = color;
                landmarkCtx.fill();
            });
        }

        function drawConnections(points, connections, color) {
            landmarkCtx.lineWidth = 2;
            landmarkCtx.strokeStyle = color;
            connections.forEach(([i, j]) => {
                if (points[i] && points[j]) {
                    landmarkCtx.beginPath();
                    landmarkCtx.moveTo(mx(points[i].x), my(points[i].y));
                    landmarkCtx.lineTo(mx(points[j].x), my(points[j].y));
                    landmarkCtx.stroke();
                }
            });
        }

        if (landmarks.left_hand) {
            drawConnections(landmarks.left_hand, HAND_CONNECTIONS, 'rgba(121,44,250,0.8)');
            drawPoints(landmarks.left_hand, '#7a2cfa', 4);
        }

        if (landmarks.right_hand) {
            drawConnections(landmarks.right_hand, HAND_CONNECTIONS, 'rgba(245,117,66,0.8)');
            drawPoints(landmarks.right_hand, '#f57542', 4);
        }

        if (landmarks.pose) {
            drawConnections(landmarks.pose, POSE_CONNECTIONS, 'rgba(0,255,136,0.6)');
            POSE_CONNECTIONS.flat().filter((v,i,a) => a.indexOf(v) === i).forEach(i => {
                if (landmarks.pose[i]) {
                    landmarkCtx.beginPath();
                    landmarkCtx.arc(mx(landmarks.pose[i].x), my(landmarks.pose[i].y), 4, 0, 2 * Math.PI);
                    landmarkCtx.fillStyle = '#00ff88';
                    landmarkCtx.fill();
                }
            });
        }
    }

    landmarkToggle.addEventListener('click', () => {
        showLandmarks = !showLandmarks;
        landmarkToggle.textContent = showLandmarks ? '👁 Landmarks ON' : '👁 Landmarks OFF';
        landmarkToggle.className = showLandmarks ? 'toggle-btn active' : 'toggle-btn';
        if (!showLandmarks) {
            landmarkCtx.clearRect(0, 0, landmarkCanvas.width, landmarkCanvas.height);
        }
    });

    consentAccept.addEventListener('click', () => {
        localStorage.setItem('signbridge_consent', 'true');
        consentModal.style.display = 'none';
    });

    consentDecline.addEventListener('click', () => {
        localStorage.setItem('signbridge_consent', 'false');
        consentModal.style.display = 'none';
    });

    function showConsentModal() {
        if (localStorage.getItem('signbridge_consent') === null) {
            consentModal.style.display = 'flex';
        }
    }

    async function saveContribution(gesture, confidence) {
        try {
            await fetch(`${BACKEND_URL}/api/contribute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    gesture: gesture,
                    confidence: confidence,
                    timestamp: new Date().toISOString()
                })
            });
        } catch(err) {
            console.log('Contribution save failed:', err);
        }
    }

    function updateSentenceDisplay() {
        window._sentence = sentence;
        window._translatedSentence = translatedSentence;
        updatePresentationDisplay();
        sentenceDisplay.innerHTML = '';
        sentence.forEach((word, index) => {
            const chip = document.createElement('div');
            chip.className = 'word-chip' + (index === sentence.length - 1 ? ' newest' : '');
            chip.style.display = 'inline-flex';
            chip.style.alignItems = 'center';
            chip.style.gap = '6px';
            const text = document.createElement('span');
            text.textContent = word.toUpperCase();
            const removeBtn = document.createElement('button');
            removeBtn.textContent = '✕';
            removeBtn.style.cssText = 'background:rgba(0,0,0,0.3);border:none;color:#fff;cursor:pointer;font-size:0.65rem;padding:2px 4px;line-height:1;border-radius:3px;margin-left:2px;';
            removeBtn.title = 'Remove this word';
            removeBtn.onclick = (e) => {
                e.stopPropagation();
                sentence.splice(index, 1);
                translatedSentence.splice(index, 1);
                updateSentenceDisplay();
                updateTranslatedDisplay();
            };
            chip.appendChild(text);
            chip.appendChild(removeBtn);
            sentenceDisplay.appendChild(chip);
        });
    }

    function updateTranslatedDisplay() {
        translatedDisplay.innerHTML = '';
        if (translatedSentence.length === 0) {
            translatedDisplay.innerHTML = '<p style="color:#555555;font-size:0.9rem;">Select a language and click Translate...</p>';
            return;
        }
        translatedSentence.forEach((word, index) => {
            const chip = document.createElement('div');
            chip.className = 'word-chip translated' + (index === translatedSentence.length - 1 ? ' newest' : '');
            chip.style.display = 'inline-flex';
            chip.style.alignItems = 'center';
            chip.style.gap = '6px';
            const text = document.createElement('span');
            text.textContent = word;
            const removeBtn = document.createElement('button');
            removeBtn.textContent = '✕';
            removeBtn.style.cssText = 'background:rgba(0,0,0,0.3);border:none;color:#fff;cursor:pointer;font-size:0.65rem;padding:2px 4px;line-height:1;border-radius:3px;margin-left:2px;';
            removeBtn.title = 'Remove this word';
            removeBtn.onclick = (e) => {
                e.stopPropagation();
                sentence.splice(index, 1);
                translatedSentence.splice(index, 1);
                updateSentenceDisplay();
                updateTranslatedDisplay();
            };
            chip.appendChild(text);
            chip.appendChild(removeBtn);
            translatedDisplay.appendChild(chip);
        });
    }

    function updateConfidenceBars(data) {
        if (!data.confidence) return;
        const gestures = ['thanks', 'i love you'];
        gestures.forEach((gesture, index) => {
            const bar = document.getElementById('bar_' + index);
            const label = document.getElementById('label_' + index);
            if (bar && label) {
                let confidence = data.gesture === gesture ? data.confidence * 100 : 0;
                bar.style.width = confidence.toFixed(0) + '%';
                label.textContent = confidence.toFixed(0) + '%';
            }
        });
    }

    async function translateAll() {
        if (sentence.length === 0) { alert('No signs detected yet!'); return; }
        currentLanguage = languageSelect.value;
        if (currentLanguage === 'en') {
            translatedSentence = [...sentence];
            updateTranslatedDisplay();
            return;
        }
        translateBtn.textContent = '⏳ Translating...';
        translateBtn.disabled = true;
        translatedSentence = [];
        for (const word of sentence) {
            try {
                const response = await fetch(`${BACKEND_URL}/api/translate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: word, target_language: currentLanguage })
                });
                const data = await response.json();
                translatedSentence.push(data.translated || word);
            } catch(err) {
                translatedSentence.push(word);
            }
        }
        updateTranslatedDisplay();
        translateBtn.textContent = '🌍 Translate';
        translateBtn.disabled = false;
    }

    function speakText(text, langCode) {
        if (!text) return;
        window.speechSynthesis.cancel();
        const voices = window.speechSynthesis.getVoices();
        let selectedVoice = voices.find(v => v.lang === langCode && v.name.includes('Google'));
        if (!selectedVoice) selectedVoice = voices.find(v => v.lang === langCode);
        if (!selectedVoice) {
            const langPrefix = langCode.split('-')[0];
            selectedVoice = voices.find(v => v.lang.startsWith(langPrefix));
        }
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = langCode;
        utterance.rate = 0.9;
        if (selectedVoice) utterance.voice = selectedVoice;
        window.speechSynthesis.speak(utterance);
    }

    function speakEnglish() {
        if (sentence.length === 0) { alert('No signs detected yet!'); return; }
        speakText(sentence.join(' '), 'en-US');
    }

    function speakTranslated() {
        if (translatedSentence.length === 0) { alert('No translation yet!'); return; }
        const lang = langMap[currentLanguage] || langMap['en'];
        speakText(translatedSentence.join(' '), lang.code);
    }

    async function startCamera() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
            video = document.getElementById('videoElement');
            video.srcObject = stream;
            return true;
        } catch (err) {
            alert('Camera access denied.');
            return false;
        }
    }

    function captureFrame() {
        if (!video || !isDetecting) return;
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0);
        const frameData = canvas.toDataURL('image/jpeg', 0.7);
        socket.emit('frame', { frame: frameData });
    }

    function startSessionTimer() {
        sessionStartTime = Date.now();
        sessionTimer = setInterval(() => {
            const elapsed = Math.floor((Date.now() - sessionStartTime) / 1000);
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            document.getElementById('sessionTime').textContent = `${mins}:${secs.toString().padStart(2,'0')}`;
        }, 1000);
    }

    async function startDetection() {
        const cameraStarted = await startCamera();
        if (!cameraStarted) return;
        isDetecting = true;
        startBtn.disabled = true;
        stopBtn.disabled = false;
        statusDot.className = 'status-dot active';
        statusText.textContent = 'LIVE';
        const pd4 = document.getElementById('presStatusDot');
        const pt4 = document.getElementById('presStatusText');
        if (pd4) { pd4.style.background = '#00ff88'; pd4.style.animation = 'pulse 1.5s infinite'; }
        if (pt4) { pt4.style.color = '#00ff88'; pt4.textContent = 'LIVE'; }
        frameInterval = setInterval(captureFrame, FRAME_RATE);
        startSessionTimer();
        setTimeout(showConsentModal, 30000);
    }

    function stopDetection() {
        isDetecting = false;
        startBtn.disabled = false;
        stopBtn.disabled = true;
        statusDot.className = 'status-dot';
        statusText.textContent = 'Stopped';
        const pd3 = document.getElementById('presStatusDot');
        const pt3 = document.getElementById('presStatusText');
        if (pd3) { pd3.style.background = '#555'; pd3.style.animation = 'none'; }
        if (pt3) { pt3.style.color = '#888'; pt3.textContent = 'Stopped'; }
        if (frameInterval) { clearInterval(frameInterval); frameInterval = null; }
        if (sessionTimer) { clearInterval(sessionTimer); sessionTimer = null; }
        if (video && video.srcObject) {
            video.srcObject.getTracks().forEach(track => track.stop());
            video.srcObject = null;
        }
        landmarkCtx.clearRect(0, 0, landmarkCanvas.width, landmarkCanvas.height);
    }

    function clearSentence() {
        sentence = [];
        translatedSentence = [];
        updateSentenceDisplay();
        updateTranslatedDisplay();
    }

    startBtn.addEventListener('click', startDetection);
    stopBtn.addEventListener('click', stopDetection);
    clearBtn.addEventListener('click', clearSentence);
    speakEnBtn.addEventListener('click', speakEnglish);
    speakTransBtn.addEventListener('click', speakTranslated);
    translateBtn.addEventListener('click', translateAll);
};

function enterPresentationMode() {
    const overlay = document.getElementById('presentationOverlay');
    const presVideo = document.getElementById('presentationVideo');

    overlay.classList.add('active');

    // Show privacy placeholder instead of camera
    presVideo.style.display = 'none';
    const placeholder = document.getElementById('presCameraPlaceholder');
    if (placeholder) placeholder.style.display = 'flex';

    // Reset status
    const pd = document.getElementById('presStatusDot');
    const pt = document.getElementById('presStatusText');
    if (pd) { pd.style.background = '#555'; pd.style.animation = 'none'; }
    if (pt) { pt.style.color = '#888'; pt.textContent = 'Not Started'; }

    updatePresentationDisplay();
}

function exitPresentationMode() {
    const overlay = document.getElementById('presentationOverlay');
    const presVideo = document.getElementById('presentationVideo');
    overlay.classList.remove('active');
    // Stop camera stream
    if (presVideo.srcObject) {
        presVideo.srcObject.getTracks().forEach(t => t.stop());
        presVideo.srcObject = null;
    }
    presVideo.style.display = 'none';
    // Stop detection if running
    if (isDetecting) {
        const stopBtn = document.getElementById('stopBtn');
        if (stopBtn) stopBtn.click();
    }
}

async function translatePresentation() {
    const lang = document.getElementById('presentationLang').value;
    const langNames = { en: 'English', es: 'Spanish', fr: 'French', ar: 'Arabic', hi: 'Hindi', ja: 'Japanese' };
    document.getElementById('presentationLangLabel').textContent = langNames[lang] || 'Translation';

    if (!window._sentence || window._sentence.length === 0) return;

    const translatedEl = document.getElementById('presentationTranslated');
    translatedEl.innerHTML = '<span style="color:#555;font-size:1rem;">Translating...</span>';

    const results = [];
    for (const word of window._sentence) {
        try {
            const res = await fetch(`${BACKEND_URL}/api/translate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: word, target_language: lang })
            });
            const data = await res.json();
            results.push(data.translated || word);
        } catch(e) {
            results.push(word);
        }
    }

    window._translatedSentence = results;
    updatePresentationDisplay();
}

function clearPresentation() {
    window._sentence = [];
    window._translatedSentence = [];
    if (typeof sentence !== 'undefined') {
        sentence.length = 0;
        translatedSentence.length = 0;
    }
    updatePresentationDisplay();
    const wordsEl = document.getElementById('presentationWords');
    const translatedEl = document.getElementById('presentationTranslated');
    if (wordsEl) wordsEl.innerHTML = '<span style="color:#333;font-size:1rem;">Waiting for signs...</span>';
    if (translatedEl) translatedEl.innerHTML = '<span style="color:#333;font-size:1rem;">No translation yet...</span>';
}

function updatePresentationDisplay() {
    const wordsEl = document.getElementById('presentationWords');
    const translatedEl = document.getElementById('presentationTranslated');

    if (!wordsEl) return;

    wordsEl.innerHTML = '';
    if (window._sentence && window._sentence.length > 0) {
        window._sentence.forEach((word, index) => {
            const el = document.createElement('div');
            el.className = 'p-word';
            el.style.display = 'inline-flex';
            el.style.alignItems = 'center';
            el.style.gap = '6px';
            const txt = document.createElement('span');
            txt.textContent = word.toUpperCase();
            const removeBtn = document.createElement('button');
            removeBtn.textContent = '✕';
            removeBtn.style.cssText = 'background:rgba(0,0,0,0.3);border:none;color:#fff;cursor:pointer;font-size:0.65rem;padding:2px 5px;border-radius:3px;';
            removeBtn.onclick = () => {
                window._sentence.splice(index, 1);
                if (window._translatedSentence) window._translatedSentence.splice(index, 1);
                updatePresentationDisplay();
            };
            el.appendChild(txt);
            el.appendChild(removeBtn);
            wordsEl.appendChild(el);
        });
    } else {
        wordsEl.innerHTML = '<span style="color:#333;font-size:1rem;">Waiting for signs...</span>';
    }

    if (translatedEl) {
        translatedEl.innerHTML = '';
        if (window._translatedSentence && window._translatedSentence.length > 0) {
            window._translatedSentence.forEach((word, index) => {
                const el = document.createElement('div');
                el.className = 'p-word translated';
                el.style.display = 'inline-flex';
                el.style.alignItems = 'center';
                el.style.gap = '6px';
                const txt = document.createElement('span');
                txt.textContent = word;
                const removeBtn = document.createElement('button');
                removeBtn.textContent = '✕';
                removeBtn.style.cssText = 'background:rgba(0,0,0,0.3);border:none;color:#fff;cursor:pointer;font-size:0.65rem;padding:2px 5px;border-radius:3px;';
                removeBtn.onclick = () => {
                    if (window._sentence) window._sentence.splice(index, 1);
                    window._translatedSentence.splice(index, 1);
                    updatePresentationDisplay();
                };
                el.appendChild(txt);
                el.appendChild(removeBtn);
                translatedEl.appendChild(el);
            });
        } else {
            translatedEl.innerHTML = '<span style="color:#333;font-size:1rem;">No translation yet...</span>';
        }
    }
}



function presStopDetection() {
    const presVideo = document.getElementById('presentationVideo');
    const placeholder = document.getElementById('presCameraPlaceholder');

    // Stop camera stream
    if (presVideo.srcObject) {
        presVideo.srcObject.getTracks().forEach(t => t.stop());
        presVideo.srcObject = null;
    }
    presVideo.style.display = 'none';
    if (placeholder) placeholder.style.display = 'flex';

    // Stop detection
    const stopBtn = document.getElementById('stopBtn');
    if (stopBtn) stopBtn.click();

    setTimeout(() => {
        const pd = document.getElementById('presStatusDot');
        const pt = document.getElementById('presStatusText');
        if (pd) { pd.style.background = '#555'; pd.style.animation = 'none'; }
        if (pt) { pt.style.color = '#888'; pt.textContent = 'Stopped'; }
    }, 100);
}

function presStartDetection() {
    const presVideo = document.getElementById('presentationVideo');
    const placeholder = document.getElementById('presCameraPlaceholder');

    // Start camera stream
    navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        .then(stream => {
            presVideo.srcObject = stream;
            presVideo.play();
            presVideo.style.display = 'block';
            if (placeholder) placeholder.style.display = 'none';
        })
        .catch(err => console.log('Camera error:', err));

    // Start detection
    const startBtn = document.getElementById('startBtn');
    if (startBtn) startBtn.click();

    setTimeout(() => {
        const pd = document.getElementById('presStatusDot');
        const pt = document.getElementById('presStatusText');
        if (pd) { pd.style.background = '#ffaa00'; pd.style.animation = 'none'; }
        if (pt) { pt.style.color = '#ffaa00'; pt.textContent = 'No Hands'; }
    }, 100);
}

// Keyboard shortcut — press Escape to exit presentation mode
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') exitPresentationMode();
});
