// JARVIS Mobile PWA Client - Desktop Matched Interface & Low Latency Engine

(function () {
  // DOM Elements
  const messagesList = document.getElementById('messagesList');
  const chatContainer = document.getElementById('chatContainer');
  const userInput = document.getElementById('userInput');
  const sendBtn = document.getElementById('sendBtn');
  const micBtn = document.getElementById('micBtn');
  const statusBadge = document.getElementById('statusBadge');
  const statusText = document.getElementById('statusText');
  const actionPills = document.getElementById('actionPills');
  const cpuVital = document.getElementById('cpuVital');
  const ramVital = document.getElementById('ramVital');

  // Orb Canvas Elements
  const orbCanvas = document.getElementById('orbCanvas');
  const orbStateLabel = document.getElementById('orbStateLabel');

  // Directives Drawer Elements
  const directivesDrawer = document.getElementById('directivesDrawer');
  const directivesToggleBtn = document.getElementById('directivesToggleBtn');
  const closeDrawerBtn = document.getElementById('closeDrawerBtn');

  // Settings Modal Elements
  const settingsModal = document.getElementById('settingsModal');
  const settingsToggleBtn = document.getElementById('settingsToggleBtn');
  const closeSettingsBtn = document.getElementById('closeSettingsBtn');
  const saveSettingsBtn = document.getElementById('saveSettingsBtn');
  const resetSettingsBtn = document.getElementById('resetSettingsBtn');
  const wsHostInput = document.getElementById('wsHostInput');
  const wsTokenInput = document.getElementById('wsTokenInput');
  const ttsToggle = document.getElementById('ttsToggle');

  // App State
  let ws = null;
  let isConnected = false;
  let isListening = false;
  let currentStreamingBubble = null;
  let streamingFullText = '';
  let lastProcessedIndex = 0;
  let activeAudio = null;
  let sentenceQueue = [];
  let isSpeaking = false;
  let playbackSession = 0;
  let recognition = null;
  let orbState = 'idle';
  let thinkingTimeout = null;

  const DEFAULT_TOKEN = 'jarvis_secure_local_token_2026';

  const STATE_CONFIGS = {
    idle: { speed: 0.003, jitter: 2, r: 167, g: 139, b: 250, text: 'IDLE' },
    thinking: { speed: 0.012, jitter: 14, r: 255, g: 165, b: 2, text: 'PROCESSING' },
    speaking: { speed: 0.007, jitter: 6, r: 46, g: 213, b: 115, text: 'SPEAKING' },
    listening: { speed: 0.008, jitter: 8, r: 255, g: 71, b: 87, text: 'LISTENING' }
  };

  // -------------------------------------------------------------
  // 1. ANIMATED 3D NODE NETWORK ORB VISUALIZER
  // -------------------------------------------------------------
  function initOrbVisualizer() {
    if (!orbCanvas) return;
    const ctx = orbCanvas.getContext('2d');
    if (!ctx) return;

    orbCanvas.width = 400;
    orbCanvas.height = 400;

    const N = 160;
    const particles = [];
    for (let i = 0; i < N; i++) {
      const u = Math.random();
      const v = Math.random();
      const theta = 2 * Math.PI * u;
      const phi = Math.acos(2 * v - 1);
      const r = 130 + Math.random() * 15;
      const tw = Math.random() * Math.PI * 2;
      particles.push({ theta, phi, r, tw });
    }

    let rot = 0;

    function renderFrame() {
      const cfg = STATE_CONFIGS[orbState] || STATE_CONFIGS.idle;
      const { speed, jitter, r, g, b, text } = cfg;

      rot += speed;

      const W = orbCanvas.width;
      const H = orbCanvas.height;
      const centerX = W / 2;
      const centerY = H / 2;

      ctx.clearRect(0, 0, W, H);

      // Soft radial glow
      const glow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, 150);
      glow.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.3)`);
      glow.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(centerX, centerY, 150, 0, Math.PI * 2);
      ctx.fill();

      // Spatial Grid Optimization
      const GRID_SIZE = 8;
      const CELL_SIZE = 50;
      const grid = Array.from({ length: GRID_SIZE }, () => Array.from({ length: GRID_SIZE }, () => []));

      const projected = new Array(particles.length);
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        const t = p.theta + rot;
        const rr = p.r + Math.sin(p.tw + rot * 4) * jitter;
        const x = rr * Math.sin(p.phi) * Math.cos(t);
        const y = rr * Math.sin(p.phi) * Math.sin(t);
        const z = rr * Math.cos(p.phi);
        const scale = 220 / (220 - z);
        const sx = centerX + x * scale * 0.95;
        const sy = centerY + y * scale * 0.95;
        const alpha = Math.max(0.08, Math.min(0.9, (z + 160) / 320));
        const size = Math.max(0.4, 1.4 * scale * 0.5);

        projected[i] = { sx, sy, alpha, size };

        const gx = Math.max(0, Math.min(GRID_SIZE - 1, Math.floor(sx / CELL_SIZE)));
        const gy = Math.max(0, Math.min(GRID_SIZE - 1, Math.floor(sy / CELL_SIZE)));
        grid[gx][gy].push(i);

        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
        ctx.beginPath();
        ctx.arc(sx, sy, size, 0, Math.PI * 2);
        ctx.fill();
      }

      // Draw connections
      const maxDistSq = 32 * 32;
      ctx.lineWidth = 0.6;
      for (let gx = 0; gx < GRID_SIZE; gx++) {
        for (let gy = 0; gy < GRID_SIZE; gy++) {
          const cell = grid[gx][gy];
          if (cell.length === 0) continue;

          for (let dx = 0; dx <= 1; dx++) {
            for (let dy = -1; dy <= 1; dy++) {
              if (dx === 0 && dy < 0) continue;
              const ngx = gx + dx;
              const ngy = gy + dy;
              if (ngx < 0 || ngx >= GRID_SIZE || ngy < 0 || ngy >= GRID_SIZE) continue;

              const neighborCell = grid[ngx][ngy];
              for (let i = 0; i < cell.length; i++) {
                const idxA = cell[i];
                const pA = projected[idxA];
                const startJ = (ngx === gx && ngy === gy) ? i + 1 : 0;

                for (let j = startJ; j < neighborCell.length; j++) {
                  const idxB = neighborCell[j];
                  const pB = projected[idxB];
                  const distSq = (pA.sx - pB.sx) ** 2 + (pA.sy - pB.sy) ** 2;
                  if (distSq < maxDistSq) {
                    const lineAlpha = (1 - Math.sqrt(distSq) / 32) * Math.min(pA.alpha, pB.alpha) * 0.35;
                    if (lineAlpha > 0.02) {
                      ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${lineAlpha})`;
                      ctx.beginPath();
                      ctx.moveTo(pA.sx, pA.sy);
                      ctx.lineTo(pB.sx, pB.sy);
                      ctx.stroke();
                    }
                  }
                }
              }
            }
          }
        }
      }

      requestAnimationFrame(renderFrame);
    }

    renderFrame();
  }

  function setOrbState(state) {
    orbState = state;
    const cfg = STATE_CONFIGS[state] || STATE_CONFIGS.idle;
    if (orbStateLabel) {
      orbStateLabel.textContent = cfg.text;
      orbStateLabel.style.color = `rgb(${cfg.r}, ${cfg.g}, ${cfg.b})`;
    }
  }

  // -------------------------------------------------------------
  // 2. SETTINGS & HARDWARE VITALS
  // -------------------------------------------------------------
  function getWsHost() {
    const saved = localStorage.getItem('jarvis_ws_host');
    if (saved && saved.trim()) return saved.trim();
    if (window.location.host) return window.location.host;
    return '127.0.0.1:8765';
  }

  function getWsToken() {
    const saved = localStorage.getItem('jarvis_ws_token');
    return (saved && saved.trim() && saved.trim() !== DEFAULT_TOKEN) ? saved.trim() : DEFAULT_TOKEN;
  }

  function getTtsEnabled() {
    const saved = localStorage.getItem('jarvis_tts_enabled');
    return saved !== null ? saved === 'true' : true;
  }

  wsHostInput.value = localStorage.getItem('jarvis_ws_host') || '';
  wsTokenInput.value = getWsToken();
  ttsToggle.checked = getTtsEnabled();

  async function fetchVitals() {
    try {
      const host = getWsHost();
      const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
      const res = await fetch(`${httpProto}://${host}/vitals`);
      if (res.ok) {
        const data = await res.json();
        if (data.cpu_usage !== undefined) cpuVital.textContent = `CPU: ${data.cpu_usage}%`;
        if (data.ram_usage !== undefined) ramVital.textContent = `RAM: ${data.ram_usage}%`;
      }
    } catch (e) {}
  }
  setInterval(fetchVitals, 5000);
  fetchVitals();

  // -------------------------------------------------------------
  // 3. LOW LATENCY SENTENCE-BY-SENTENCE TTS ENGINE
  // -------------------------------------------------------------
  function stopSpeech() {
    playbackSession += 1;
    if (activeAudio) {
      try {
        activeAudio.pause();
        activeAudio.currentTime = 0;
      } catch (e) {}
      activeAudio = null;
    }
    sentenceQueue = [];
    isSpeaking = false;
    streamingFullText = '';
    lastProcessedIndex = 0;
    setOrbState('idle');
  }

  function cleanTextForSpeech(rawText) {
    if (!rawText) return '';
    return rawText
      .replace(/```[\s\S]*?```/g, '')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/https?:\/\/\S+/g, '')
      .replace(/[*_#~>]/g, '')
      .replace(/^[\s-*+•\d.]+/gm, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  async function processNextSentence() {
    const currentSession = playbackSession;

    if (sentenceQueue.length === 0) {
      isSpeaking = false;
      setOrbState('idle');
      return;
    }

    isSpeaking = true;
    const text = sentenceQueue.shift();
    if (!text) {
      processNextSentence();
      return;
    }

    if (!getTtsEnabled()) {
      processNextSentence();
      return;
    }

    try {
      const host = getWsHost();
      const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
      const res = await fetch(`${httpProto}://${host}/tts_sentence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sentence: text })
      });

      if (currentSession !== playbackSession) return;

      if (res.ok) {
        const data = await res.json();
        if (data.audio) {
          const audio = new Audio(data.audio);
          activeAudio = audio;
          audio.onplay = () => {
            if (currentSession === playbackSession) setOrbState('speaking');
          };
          audio.onended = () => {
            activeAudio = null;
            if (currentSession === playbackSession) processNextSentence();
          };
          audio.onerror = () => {
            activeAudio = null;
            if (currentSession === playbackSession) processNextSentence();
          };
          setOrbState('speaking');
          audio.play().catch(() => processNextSentence());
          return;
        }
      }
    } catch (e) {}

    // Fallback Web Speech API
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.onstart = () => { setOrbState('speaking'); };
      utterance.onend = () => { if (currentSession === playbackSession) processNextSentence(); };
      utterance.onerror = () => { if (currentSession === playbackSession) processNextSentence(); };
      window.speechSynthesis.speak(utterance);
    } else {
      processNextSentence();
    }
  }

  function enqueueSentence(sentenceText) {
    const clean = cleanTextForSpeech(sentenceText);
    if (clean) {
      sentenceQueue.push(clean);
      if (!isSpeaking) processNextSentence();
    }
  }

  // -------------------------------------------------------------
  // 4. MARKDOWN & CODE BLOCK FORMATTER
  // -------------------------------------------------------------
  function renderMarkdown(rawText) {
    if (!rawText) return '';
    let escaped = rawText
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Fenced Code Blocks ```lang ... ```
    escaped = escaped.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
      const codeLang = lang || 'code';
      return `<pre><button class="copy-code-btn" onclick="navigator.clipboard.writeText(this.nextElementSibling.innerText)">Copy</button><code>${code.trim()}</code></pre>`;
    });

    // Inline Code `code`
    escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold **text**
    escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Italic *text*
    escaped = escaped.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Line breaks
    escaped = escaped.replace(/\n/g, '<br>');

    return escaped;
  }

  function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  function getTimeStr() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  }

  function appendMessage(role, text, options = {}) {
    const msgRow = document.createElement('div');
    msgRow.className = `msg-row ${role}${options.isAlert ? ' alert' : ''}`;

    const msgHeader = document.createElement('div');
    msgHeader.className = 'msg-header';
    msgHeader.innerHTML = `<span>${role === 'user' ? 'YOU' : 'JARVIS'}</span> · <span>${getTimeStr()}</span>`;
    msgRow.appendChild(msgHeader);

    const msgBubble = document.createElement('div');
    msgBubble.className = 'msg-bubble';
    msgBubble.innerHTML = renderMarkdown(text);
    msgRow.appendChild(msgBubble);

    if (options.toolCalls && options.toolCalls.length > 0) {
      options.toolCalls.forEach(tc => {
        const badge = document.createElement('div');
        badge.className = 'tool-badge';
        badge.textContent = `⚡ Tool Executed: ${tc.name}`;
        msgRow.appendChild(badge);
      });
    }

    if (options.isStreaming) {
      currentStreamingBubble = msgBubble;
    }

    messagesList.appendChild(msgRow);
    scrollToBottom();
    return msgRow;
  }

  function clearThinkingTimeout() {
    if (thinkingTimeout) {
      clearTimeout(thinkingTimeout);
      thinkingTimeout = null;
    }
  }

  // -------------------------------------------------------------
  // 5. WEBSOCKET CONTROLLER & MESSAGE DISPATCH
  // -------------------------------------------------------------
  async function resolveWsToken() {
    const custom = localStorage.getItem('jarvis_ws_token');
    if (custom && custom.trim() && custom.trim() !== DEFAULT_TOKEN) return custom.trim();

    try {
      const host = getWsHost();
      const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
      const res = await fetch(`${httpProto}://${host}/mobile/config.json`);
      if (res.ok) {
        const cfg = await res.json();
        if (cfg && cfg.ws_token) {
          localStorage.setItem('jarvis_ws_token', cfg.ws_token);
          wsTokenInput.value = cfg.ws_token;
          return cfg.ws_token;
        }
      }
    } catch (e) {}
    return DEFAULT_TOKEN;
  }

  async function connectWebSocket() {
    const host = getWsHost();
    const token = await resolveWsToken();
    const wsProto = window.location.protocol.startsWith('https') ? 'wss' : 'ws';
    const wsUrl = `${wsProto}://${host}/ws?token=${token}`;

    console.log(`[WS] Connecting to ${wsUrl}...`);
    statusText.textContent = 'Connecting';
    statusBadge.className = 'status-badge';
    setOrbState('idle');

    try {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('[WS] Connected to JARVIS backend.');
        isConnected = true;
        statusText.textContent = 'Connected';
        statusBadge.className = 'status-badge connected';
        setOrbState('idle');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleServerMessage(data);
        } catch (err) {}
      };

      ws.onerror = (err) => {
        console.error('[WS] Connection error:', err);
        localStorage.removeItem('jarvis_ws_token');
        statusText.textContent = 'Auth Error';
        statusBadge.className = 'status-badge disconnected';
        setOrbState('idle');
      };

      ws.onclose = () => {
        console.log('[WS] Connection closed. Retrying in 4s...');
        isConnected = false;
        statusText.textContent = 'Disconnected';
        statusBadge.className = 'status-badge disconnected';
        setOrbState('idle');
        setTimeout(connectWebSocket, 4000);
      };
    } catch (e) {
      statusText.textContent = 'Config Error';
      statusBadge.className = 'status-badge disconnected';
    }
  }

  function handleServerMessage(data) {
    if (data.type === 'status') {
      if (data.status === 'thinking') {
        clearThinkingTimeout();
        setOrbState('thinking');
        statusText.textContent = 'Thinking';
        thinkingTimeout = setTimeout(() => {
          setOrbState('idle');
          statusText.textContent = 'Connected';
          appendMessage('jarvis', 'Response timeout, sir. The backend process took longer than expected.', { isAlert: true });
        }, 60000);
      } else if (data.status === 'connected') {
        clearThinkingTimeout();
        statusText.textContent = 'Connected';
        setOrbState('idle');
        if (messagesList.children.length === 0) {
          appendMessage('jarvis', data.message || 'JARVIS online and standing by, sir.');
          enqueueSentence(data.message || 'JARVIS online and standing by, sir.');
        }
      }
    } else if (data.type === 'chunk') {
      clearThinkingTimeout();
      setOrbState('thinking');
      const chunkText = data.text || '';

      if (!currentStreamingBubble) {
        appendMessage('jarvis', chunkText, { isStreaming: true });
      } else {
        currentStreamingBubble.innerHTML = renderMarkdown(streamingFullText + chunkText);
        scrollToBottom();
      }

      streamingFullText += chunkText;
      const completed = streamingFullText.slice(lastProcessedIndex).match(/[^.!?]+[.!?]+(\s+|$)/g);
      if (completed && completed.length > 0) {
        for (const s of completed) {
          lastProcessedIndex += s.length;
          enqueueSentence(s);
        }
      }
    } else if (data.type === 'response' || data.type === 'command_response') {
      clearThinkingTimeout();
      statusText.textContent = 'Connected';
      const respText = data.text || 'Command completed, sir.';

      if (currentStreamingBubble) {
        currentStreamingBubble.innerHTML = renderMarkdown(respText);
      } else {
        appendMessage('jarvis', respText, { toolCalls: data.tool_calls });
      }

      const tailText = streamingFullText.slice(lastProcessedIndex) || respText;
      if (tailText && !sentenceQueue.length && !isSpeaking) {
        enqueueSentence(tailText);
      } else if (tailText && isSpeaking) {
        sentenceQueue.push(cleanTextForSpeech(tailText));
      }

      currentStreamingBubble = null;
      streamingFullText = '';
      lastProcessedIndex = 0;
    } else if (data.type === 'proactive_alert') {
      clearThinkingTimeout();
      const alertText = data.text || 'Proactive alert received.';
      appendMessage('jarvis', alertText, { isAlert: true });
      enqueueSentence(alertText);
    } else if (data.type === 'state_update') {
      const badge = document.createElement('div');
      badge.className = 'state-badge';
      badge.textContent = `🔄 State Update [${data.domain} -> ${data.action}]`;
      messagesList.appendChild(badge);
      scrollToBottom();
    }
  }

  function sendMessage(text) {
    stopSpeech();
    clearThinkingTimeout();

    const clean = text.trim();
    if (!clean) return;

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      appendMessage('jarvis', 'Error: Backend is disconnected.', { isAlert: true });
      return;
    }

    appendMessage('user', clean);
    setOrbState('thinking');
    statusText.textContent = 'Processing';

    thinkingTimeout = setTimeout(() => {
      setOrbState('idle');
      statusText.textContent = 'Connected';
      appendMessage('jarvis', 'Connection timeout, sir. Please check backend status.', { isAlert: true });
    }, 60000);

    if (clean.startsWith('/')) {
      ws.send(JSON.stringify({ type: 'slash_command', command: clean }));
    } else {
      ws.send(JSON.stringify({ type: 'message', message: clean }));
    }

    userInput.value = '';
    userInput.style.height = 'auto';
  }

  // -------------------------------------------------------------
  // 6. VOICE RECOGNITION & DRAWER LISTENERS
  // -------------------------------------------------------------
  function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      micBtn.style.display = 'none';
      return;
    }

    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      isListening = true;
      micBtn.className = 'mic-btn listening';
      setOrbState('listening');
    };

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      if (transcript) {
        userInput.value = transcript;
        sendMessage(transcript);
      }
    };

    recognition.onerror = () => {
      isListening = false;
      micBtn.className = 'mic-btn';
      setOrbState('idle');
    };

    recognition.onend = () => {
      isListening = false;
      micBtn.className = 'mic-btn';
      if (orbState === 'listening') setOrbState('idle');
    };
  }

  // UI Event Handlers
  sendBtn.addEventListener('click', () => sendMessage(userInput.value));

  userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(userInput.value);
    }
  });

  micBtn.addEventListener('click', () => {
    if (!recognition) return;
    if (isListening) recognition.stop();
    else recognition.start();
  });

  actionPills.addEventListener('click', (e) => {
    const pill = e.target.closest('.pill-btn');
    if (pill && pill.dataset.cmd) sendMessage(pill.dataset.cmd);
  });

  directivesToggleBtn.addEventListener('click', () => directivesDrawer.classList.remove('hidden'));
  closeDrawerBtn.addEventListener('click', () => directivesDrawer.classList.add('hidden'));

  directivesDrawer.addEventListener('click', (e) => {
    const card = e.target.closest('.protocol-card');
    if (card && card.dataset.cmd) {
      directivesDrawer.classList.add('hidden');
      sendMessage(card.dataset.cmd);
    }
  });

  settingsToggleBtn.addEventListener('click', () => settingsModal.classList.remove('hidden'));
  closeSettingsBtn.addEventListener('click', () => settingsModal.classList.add('hidden'));

  saveSettingsBtn.addEventListener('click', () => {
    const newHost = wsHostInput.value.trim();
    const newToken = wsTokenInput.value.trim();
    const newTts = ttsToggle.checked;

    if (newHost) localStorage.setItem('jarvis_ws_host', newHost);
    else localStorage.removeItem('jarvis_ws_host');

    if (newToken) localStorage.setItem('jarvis_ws_token', newToken);
    else localStorage.removeItem('jarvis_ws_token');

    localStorage.setItem('jarvis_tts_enabled', newTts ? 'true' : 'false');
    settingsModal.classList.add('hidden');
    if (ws) ws.close();
  });

  resetSettingsBtn.addEventListener('click', () => {
    localStorage.removeItem('jarvis_ws_host');
    localStorage.removeItem('jarvis_ws_token');
    localStorage.setItem('jarvis_tts_enabled', 'true');
    wsHostInput.value = '';
    wsTokenInput.value = DEFAULT_TOKEN;
    ttsToggle.checked = true;
  });

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('sw.js').catch(() => {});
    });
  }

  // Launch App & Visualizer
  initOrbVisualizer();
  initSpeechRecognition();
  connectWebSocket();
})();
