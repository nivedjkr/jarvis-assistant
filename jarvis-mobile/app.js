// JARVIS Mobile PWA Client - Desktop Matched Interface & Low Latency Engine
// Mark 5.9 Stark Command Deck, Multi-Agent Switcher, Visual Diff Inspector & Touch Ergonomics

(function () {
  // DOM Elements - Main Layout & Controls
  const messagesList = document.getElementById('messagesList');
  const chatContainer = document.getElementById('chatContainer');
  const inputContainer = document.getElementById('inputContainer');
  const userInput = document.getElementById('userInput');
  const sendBtn = document.getElementById('sendBtn');
  const micBtn = document.getElementById('micBtn');
  const statusBadge = document.getElementById('statusBadge');
  const statusText = document.getElementById('statusText');
  const actionPills = document.getElementById('actionPills');
  const cpuVital = document.getElementById('cpuVital');
  const ramVital = document.getElementById('ramVital');
  const activeToolBar = document.getElementById('activeToolBar');
  const activeToolText = document.getElementById('activeToolText');

  // Orb Canvas & Collapsible Elements
  const orbContainer = document.getElementById('orbContainer');
  const orbCanvas = document.getElementById('orbCanvas');
  const orbStateLabel = document.getElementById('orbStateLabel');
  const orbToggleBtn = document.getElementById('orbToggleBtn');

  // Persona Badge & Switcher Modal Elements
  const personaBadgeBtn = document.getElementById('personaBadgeBtn');
  const personaEmoji = document.getElementById('personaEmoji');
  const personaName = document.getElementById('personaName');
  const personaModal = document.getElementById('personaModal');
  const closePersonaBtn = document.getElementById('closePersonaBtn');
  const personaGrid = document.getElementById('personaGrid');

  // Command Deck Drawer Elements
  const commandDeckDrawer = document.getElementById('commandDeckDrawer');
  const deckToggleBtn = document.getElementById('deckToggleBtn');
  const closeDeckBtn = document.getElementById('closeDeckBtn');
  const tabDirectivesBtn = document.getElementById('tabDirectivesBtn');
  const tabDispatchesBtn = document.getElementById('tabDispatchesBtn');
  const tabMissionsBtn = document.getElementById('tabMissionsBtn');
  const paneDirectives = document.getElementById('paneDirectives');
  const paneDispatches = document.getElementById('paneDispatches');
  const paneMissions = document.getElementById('paneMissions');

  // Command Deck Sub-components
  const newDirectiveInput = document.getElementById('newDirectiveInput');
  const addDirectiveBtn = document.getElementById('addDirectiveBtn');
  const refreshDirectivesBtn = document.getElementById('refreshDirectivesBtn');
  const directivesContainer = document.getElementById('directivesContainer');
  const dispInboxBtn = document.getElementById('dispInboxBtn');
  const dispSentBtn = document.getElementById('dispSentBtn');
  const refreshDispatchesBtn = document.getElementById('refreshDispatchesBtn');
  const dispatchesContainer = document.getElementById('dispatchesContainer');
  const refreshMissionsBtn = document.getElementById('refreshMissionsBtn');
  const missionsContainer = document.getElementById('missionsContainer');
  const deckMissionsPill = document.getElementById('deckMissionsPill');

  // Visual Diff Inspector Modal Elements
  const diffModal = document.getElementById('diffModal');
  const closeDiffBtn = document.getElementById('closeDiffBtn');
  const diffStatBadge = document.getElementById('diffStatBadge');
  const diffPathText = document.getElementById('diffPathText');
  const copyDiffBtn = document.getElementById('copyDiffBtn');
  const refreshDiffBtn = document.getElementById('refreshDiffBtn');
  const diffModalCode = document.getElementById('diffModalCode');

  // Sessions Drawer Elements
  const sessionsDrawer = document.getElementById('sessionsDrawer');
  const sessionsToggleBtn = document.getElementById('sessionsToggleBtn');
  const closeSessionsBtn = document.getElementById('closeSessionsBtn');
  const newSessionBtn = document.getElementById('newSessionBtn');
  const sessionsList = document.getElementById('sessionsList');

  // Settings Modal Elements
  const settingsModal = document.getElementById('settingsModal');
  const settingsToggleBtn = document.getElementById('settingsToggleBtn');
  const closeSettingsBtn = document.getElementById('closeSettingsBtn');
  const saveSettingsBtn = document.getElementById('saveSettingsBtn');
  const resetSettingsBtn = document.getElementById('resetSettingsBtn');
  const wsHostInput = document.getElementById('wsHostInput');
  const wsTokenInput = document.getElementById('wsTokenInput');
  const ttsToggle = document.getElementById('ttsToggle');
  const mobileHandsFreeBtn = document.getElementById('mobileHandsFreeBtn');
  const mobileCameraBtn = document.getElementById('mobileCameraBtn');
  const mobileCameraInput = document.getElementById('mobileCameraInput');
  const mobileInputCamBtn = document.getElementById('mobileInputCamBtn');

  // Stark Web Audio Synthesizer (Zero-latency hardware chimes)
  function playStarkChime(type) {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      if (ctx.state === 'suspended') ctx.resume();
      const now = ctx.currentTime;

      if (type === 'wake') {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.exponentialRampToValueAtTime(1760, now + 0.12);
        gain.gain.setValueAtTime(0.3, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.35);
      } else if (type === 'ack') {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(523.25, now);
        osc.frequency.setValueAtTime(659.25, now + 0.08);
        gain.gain.setValueAtTime(0.25, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.25);
      } else if (type === 'done') {
        [659.25, 880.0, 1318.5].forEach((freq, i) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          osc.type = 'sine';
          osc.frequency.setValueAtTime(freq, now + i * 0.07);
          gain.gain.setValueAtTime(0.2, now + i * 0.07);
          gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.07 + 0.3);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(now + i * 0.07);
          osc.stop(now + i * 0.07 + 0.3);
        });
      } else if (type === 'alert') {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(370, now + 0.15);
        gain.gain.setValueAtTime(0.3, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.3);
      }
    } catch (e) {
      console.warn('Stark chime error:', e);
    }
  }

  // App State
  let ws = null;
  let isConnected = false;
  let isListening = false;
  let isHandsFreeActive = false;
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
  let mobilePingInterval = null;
  let currentRawDiff = '';
  let activeAgentId = 'jarvis';
  let currentDeckTab = 'directives';
  let emailDeckMode = 'inbox';
  let isOrbCollapsed = false;

  const DEFAULT_TOKEN = 'jarvis_secure_local_token_2026';
  const BIG_JOB_TIMEOUT_MS = 180000; // 180 seconds matching desktop engine

  let currentSessionId = localStorage.getItem('jarvis_session_id');
  if (!currentSessionId) {
    currentSessionId = 'mobile_' + Math.random().toString(36).substring(2, 10);
    localStorage.setItem('jarvis_session_id', currentSessionId);
  }

  // Built-in Agent Personas
  const AGENT_PERSONAS = [
    {
      id: 'jarvis',
      name: 'J.A.R.V.I.S.',
      emoji: '⚡',
      role: 'Supreme Butler & General Assistant',
      desc: 'Calm dry British wit. Master of multi-step task delegation, developer workflows & general assistance.',
      model: 'nvidia/nemotron-3-super-120b-a12b',
      badgeClass: ''
    },
    {
      id: 'ultron',
      name: 'ULTRON',
      emoji: '🔴',
      role: 'Autonomous Architect & Offensive Debugger',
      desc: 'Cold, ruthless, hyper-efficient. Demands flawless code architecture, high-speed refactoring & offensive debugging.',
      model: 'nvidia/nemotron-3-ultra-550b-a55b',
      badgeClass: 'ultron'
    },
    {
      id: 'friday',
      name: 'F.R.I.D.A.Y.',
      emoji: '🟢',
      role: 'Tactical HUD Liaison & Rapid Research',
      desc: 'Warm energetic Irish cadence. Fast-path web intelligence, live telemetry & proactive tactical feedback.',
      model: 'meta/llama-3.2-11b-vision-instruct',
      badgeClass: 'friday'
    },
    {
      id: 'edith',
      name: 'E.D.I.T.H.',
      emoji: '🔵',
      role: 'Strategic Sentinel & Perimeter Security',
      desc: 'Tactical security audit, secret scanning, repository quarantine, perimeter defense & situational awareness.',
      model: 'nvidia/nemotron-3-super-120b-a12b',
      badgeClass: 'edith'
    },
    {
      id: 'karen',
      name: 'K.A.R.E.N.',
      emoji: '🟣',
      role: 'Workshop Supervisor & Telemetry Watchdog',
      desc: 'Empathetic workshop supervisor. Telemetry tracking, hardware watchdog & battery optimization.',
      model: 'nvidia/nemotron-3-super-120b-a12b',
      badgeClass: 'karen'
    }
  ];

  const STATE_CONFIGS = {
    idle: { speed: 0.003, jitter: 2, r: 255, g: 255, b: 255, glowAlpha: 0.12, text: 'IDLE' },
    thinking: { speed: 0.014, jitter: 14, r: 255, g: 255, b: 255, glowAlpha: 0.28, text: 'PROCESSING' },
    speaking: { speed: 0.009, jitter: 6, r: 255, g: 255, b: 255, glowAlpha: 0.22, text: 'SPEAKING' },
    listening: { speed: 0.007, jitter: 8, r: 255, g: 255, b: 255, glowAlpha: 0.22, text: 'LISTENING' }
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
      if (isOrbCollapsed) {
        requestAnimationFrame(renderFrame);
        return;
      }

      const cfg = STATE_CONFIGS[orbState] || STATE_CONFIGS.idle;
      const { speed, jitter, r, g, b, glowAlpha = 0.12 } = cfg;

      rot += speed;

      const W = orbCanvas.width;
      const H = orbCanvas.height;
      const centerX = W / 2;
      const centerY = H / 2;

      ctx.clearRect(0, 0, W, H);

      // Radial glow
      const glow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, 150);
      glow.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${glowAlpha})`);
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
      orbStateLabel.style.color = '#ffffff';
      orbStateLabel.style.opacity = state === 'idle' ? '0.75' : '1';
    }
  }

  function toggleOrbCollapse(forceCollapse) {
    if (typeof forceCollapse === 'boolean') {
      isOrbCollapsed = forceCollapse;
    } else {
      isOrbCollapsed = !isOrbCollapsed;
    }

    if (orbContainer) {
      if (isOrbCollapsed) {
        orbContainer.classList.add('collapsed');
        if (orbToggleBtn) orbToggleBtn.textContent = '▼';
      } else {
        orbContainer.classList.remove('collapsed');
        if (orbToggleBtn) orbToggleBtn.textContent = '▲';
      }
    }
  }

  // -------------------------------------------------------------
  // 2. MULTI-AGENT PERSONA REGISTRY
  // -------------------------------------------------------------
  async function fetchAgents() {
    try {
      const host = getWsHost();
      const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
      const res = await fetch(`${httpProto}://${host}/agents`);
      if (res.ok) {
        const data = await res.json();
        if (data.active_agent) {
          setActivePersonaUI(data.active_agent);
        }
      }
    } catch (e) {}
  }

  function setActivePersonaUI(agentId) {
    activeAgentId = agentId.toLowerCase();
    const persona = AGENT_PERSONAS.find(p => p.id === activeAgentId) || AGENT_PERSONAS[0];

    if (personaBadgeBtn) {
      personaBadgeBtn.className = `persona-badge-btn ${persona.badgeClass}`;
      if (personaEmoji) personaEmoji.textContent = persona.emoji;
      if (personaName) personaName.textContent = persona.name;
    }

    renderPersonaGrid();
  }

  function renderPersonaGrid() {
    if (!personaGrid) return;
    personaGrid.innerHTML = '';

    AGENT_PERSONAS.forEach(p => {
      const card = document.createElement('div');
      card.className = `persona-card ${p.id} ${p.id === activeAgentId ? 'active' : ''}`;
      card.innerHTML = `
        <div class="persona-card-emoji">${p.emoji}</div>
        <div class="persona-card-details">
          <div class="persona-card-header">
            <span class="persona-card-name">${p.name}</span>
            <span class="persona-card-role">${p.role}</span>
          </div>
          <div class="persona-card-desc">${p.desc}</div>
        </div>
      `;

      card.addEventListener('click', () => {
        switchPersona(p.id);
      });

      personaGrid.appendChild(card);
    });
  }

  async function switchPersona(agentId) {
    try {
      const host = getWsHost();
      const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
      await fetch(`${httpProto}://${host}/agents/switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId })
      });

      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'slash_command', command: `/agent switch ${agentId}` }));
      }

      setActivePersonaUI(agentId);
      playStarkChime('ack');
      if (personaModal) personaModal.classList.add('hidden');
    } catch (err) {
      console.warn('Error switching persona:', err);
    }
  }

  // -------------------------------------------------------------
  // 3. SETTINGS & HARDWARE VITALS
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
  // 4. LOW LATENCY SENTENCE-BY-SENTENCE TTS ENGINE
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

  function prefetchNextSentence(item) {
    if (!item || item.audioPromise || item.audioData || !getTtsEnabled()) return;
    const text = typeof item === 'string' ? item : item.text;
    if (!text) return;
    try {
      const host = getWsHost();
      const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
      item.audioPromise = fetch(`${httpProto}://${host}/tts_sentence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sentence: text })
      })
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data && data.audio) {
          item.audioData = data.audio;
          return data.audio;
        }
        return null;
      })
      .catch(err => {
        console.warn('Mobile TTS prefetch error:', err);
        return null;
      });
    } catch (e) {}
  }

  async function processNextSentence() {
    const currentSession = playbackSession;

    if (sentenceQueue.length === 0) {
      isSpeaking = false;
      setOrbState('idle');
      return;
    }

    isSpeaking = true;
    const item = sentenceQueue.shift();
    if (!item) {
      processNextSentence();
      return;
    }

    const text = typeof item === 'string' ? item : item.text;
    if (!text) {
      processNextSentence();
      return;
    }

    if (!getTtsEnabled()) {
      processNextSentence();
      return;
    }

    if (sentenceQueue.length > 0) {
      prefetchNextSentence(sentenceQueue[0]);
    }

    try {
      let audioBase64 = typeof item === 'object' ? item.audioData : null;
      if (!audioBase64 && typeof item === 'object' && item.audioPromise) {
        audioBase64 = await item.audioPromise;
      }

      if (!audioBase64) {
        const host = getWsHost();
        const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
        const res = await fetch(`${httpProto}://${host}/tts_sentence`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sentence: text })
        });
        if (res.ok) {
          const data = await res.json();
          if (data && data.audio) {
            audioBase64 = data.audio;
          }
        }
      }

      if (currentSession !== playbackSession) return;

      if (audioBase64) {
        const audio = new Audio(audioBase64);
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
      const item = { text: clean };
      sentenceQueue.push(item);
      if (!isSpeaking) {
        processNextSentence();
      } else if (sentenceQueue.length === 1) {
        prefetchNextSentence(item);
      }
    }
  }

  // -------------------------------------------------------------
  // 5. MARKDOWN FORMATTER & DIFF/CONFIRMATION CARDS
  // -------------------------------------------------------------
  function renderMarkdown(rawText) {
    if (!rawText) return '';
    let escaped = rawText
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Fenced Code Blocks with Inspect Diff button
    escaped = escaped.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
      const isDiff = lang === 'diff' || code.includes('--- a/') || code.includes('+++ b/');
      const diffBtnHtml = isDiff ? `<button class="inspect-diff-btn" onclick="window.jarvisOpenDiffFromCode(this)">INSPECT DIFF</button>` : '';
      return `<pre><div class="code-actions-header">${diffBtnHtml}<button class="copy-code-btn" onclick="navigator.clipboard.writeText(this.parentElement.nextElementSibling.innerText)">Copy</button></div><code>${code.trim()}</code></pre>`;
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

  // Window helper for inline Inspect Diff buttons
  window.jarvisOpenDiffFromCode = function (btn) {
    const pre = btn.closest('pre');
    if (!pre) return;
    const code = pre.querySelector('code');
    if (code) {
      renderDiffViewer(code.innerText, 'Custom Diff Preview', 'Workspace Patch');
    }
  };

  function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  function getTimeStr() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  }

  function appendMessage(role, text, options = {}) {
    const msgRow = document.createElement('div');
    msgRow.className = `msg-row ${role}${options.isAlert ? ' alert' : ''}`;

    const persona = AGENT_PERSONAS.find(p => p.id === activeAgentId) || AGENT_PERSONAS[0];
    const roleLabel = role === 'user' ? 'YOU' : `${persona.name.split('.')[0] || persona.name} // MK 5.9`;

    const msgHeader = document.createElement('div');
    msgHeader.className = 'msg-header';
    msgHeader.innerHTML = `<span>${roleLabel}</span> · <span>${getTimeStr()}</span>`;
    msgRow.appendChild(msgHeader);

    const msgBubble = document.createElement('div');
    msgBubble.className = 'msg-bubble';
    msgBubble.innerHTML = renderMarkdown(text);

    // Check for PENDING_CONFIRMATION safety gate
    const confirmMatch = text.match(/PENDING_CONFIRMATION:\s*Action ID:\s*(\w+)[\s\S]*?Tool:\s*([^\n]+)[\s\S]*?Preview:\s*([^\n]+)/);
    if (confirmMatch) {
      const actId = confirmMatch[1];
      const toolName = confirmMatch[2].trim();
      const previewText = confirmMatch[3].trim();

      const actionCard = document.createElement('div');
      actionCard.className = 'pending-action-card';
      actionCard.innerHTML = `
        <div class="action-header">
          <span>⚠️ SAFETY CONFIRMATION REQUIRED</span>
          <span>#${actId}</span>
        </div>
        <div class="action-preview"><strong>${toolName}</strong>: ${previewText}</div>
        <div class="action-buttons">
          <button class="btn-confirm-action" data-act="${actId}">✓ CONFIRM & EXECUTE</button>
          <button class="btn-cancel-action" data-act="${actId}">✕ CANCEL</button>
        </div>
      `;

      actionCard.querySelector('.btn-confirm-action').addEventListener('click', () => {
        actionCard.querySelector('.btn-confirm-action').disabled = true;
        actionCard.querySelector('.btn-confirm-action').textContent = 'EXECUTING...';
        playStarkChime('ack');
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'confirm_action', action_id: actId }));
        }
      });

      actionCard.querySelector('.btn-cancel-action').addEventListener('click', () => {
        actionCard.remove();
        sendMessage(`/confirm cancel`);
      });

      msgBubble.appendChild(actionCard);
    }

    if (options.imageUrl) {
      const img = document.createElement('img');
      img.src = options.imageUrl;
      img.style.maxWidth = '100%';
      img.style.maxHeight = '220px';
      img.style.borderRadius = '8px';
      img.style.marginTop = '8px';
      img.style.display = 'block';
      img.style.objectFit = 'contain';
      msgBubble.appendChild(img);
    }

    msgRow.appendChild(msgBubble);

    if (options.toolCalls && options.toolCalls.length > 0) {
      options.toolCalls.forEach(tc => {
        const badge = document.createElement('div');
        badge.className = 'tool-badge';
        const isDiffTool = tc.name === 'git_diff' || tc.name === 'inspect_and_edit_archive';
        badge.innerHTML = `<span>// Tool: ${tc.name}</span>`;
        if (isDiffTool) {
          const diffBtn = document.createElement('button');
          diffBtn.className = 'tool-diff-btn';
          diffBtn.textContent = 'DIFF';
          diffBtn.addEventListener('click', () => openWorkspaceDiff());
          badge.appendChild(diffBtn);
        }
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

  function resetThinkingTimeout() {
    clearThinkingTimeout();
    thinkingTimeout = setTimeout(() => {
      setOrbState('idle');
      statusText.textContent = 'Connected';
      hideActiveToolBanner();
      appendMessage('jarvis', 'Response timeout, sir. The operation is running in the background.', { isAlert: true });
    }, BIG_JOB_TIMEOUT_MS);
  }

  function clearThinkingTimeout() {
    if (thinkingTimeout) {
      clearTimeout(thinkingTimeout);
      thinkingTimeout = null;
    }
  }

  function showActiveToolBanner(text) {
    if (activeToolBar) {
      activeToolBar.classList.remove('hidden');
      if (activeToolText) activeToolText.textContent = text || 'JARVIS is thinking...';
    }
  }

  function hideActiveToolBanner() {
    if (activeToolBar) {
      activeToolBar.classList.add('hidden');
    }
  }

  // -------------------------------------------------------------
  // 6. WEBSOCKET CONTROLLER & MESSAGE DISPATCH
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
    const wsUrl = `${wsProto}://${host}/ws?token=${token}&session_id=${currentSessionId}`;

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

        if (mobilePingInterval) clearInterval(mobilePingInterval);
        mobilePingInterval = setInterval(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 25000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleServerMessage(data);
        } catch (err) {}
      };

      ws.onerror = (err) => {
        if (mobilePingInterval) clearInterval(mobilePingInterval);
        console.error('[WS] Connection error:', err);
        localStorage.removeItem('jarvis_ws_token');
        statusText.textContent = 'Auth Error';
        statusBadge.className = 'status-badge disconnected';
        setOrbState('idle');
      };

      ws.onclose = () => {
        if (mobilePingInterval) clearInterval(mobilePingInterval);
        console.log('[WS] Connection closed. Retrying in 4s...');
        isConnected = false;
        statusText.textContent = 'Disconnected';
        statusBadge.className = 'status-badge disconnected';
        setOrbState('idle');
        hideActiveToolBanner();
        setTimeout(connectWebSocket, 4000);
      };
    } catch (e) {
      statusText.textContent = 'Config Error';
      statusBadge.className = 'status-badge disconnected';
    }
  }

  function handleServerMessage(data) {
    if (data.sound) {
      playStarkChime(data.sound);
    }

    if (data.type === 'wake_detected') {
      stopSpeech();
      playStarkChime('wake');
      setOrbState('listening');
      statusText.textContent = 'Wake Detected';
      appendMessage('jarvis', 'JARVIS is listening, sir...', { isAlert: false });
      return;
    } else if (data.type === 'barge_in') {
      stopSpeech();
      setOrbState('listening');
      return;
    } else if (data.type === 'handsfree_status') {
      isHandsFreeActive = !!data.active;
      if (mobileHandsFreeBtn) {
        if (isHandsFreeActive) {
          mobileHandsFreeBtn.classList.add('active');
          mobileHandsFreeBtn.textContent = 'Hands-Free ON';
        } else {
          mobileHandsFreeBtn.classList.remove('active');
          mobileHandsFreeBtn.textContent = 'Hands-Free';
        }
      }
      return;
    } else if (data.type === 'handsfree_command') {
      appendMessage('user', data.text || '');
      setOrbState('thinking');
      statusText.textContent = 'Processing';
      resetThinkingTimeout();
      return;
    } else if (data.type === 'status') {
      if (data.status === 'thinking') {
        resetThinkingTimeout();
        setOrbState('thinking');
        statusText.textContent = 'Thinking';
        if (data.active_tool) {
          showActiveToolBanner(`Executing tool: ${data.active_tool}...`);
        } else if (data.message) {
          showActiveToolBanner(data.message);
        } else {
          showActiveToolBanner('JARVIS is thinking...');
        }
      } else if (data.status === 'connected') {
        clearThinkingTimeout();
        hideActiveToolBanner();
        statusText.textContent = 'Connected';
        setOrbState('idle');
        if (data.session_id) {
          currentSessionId = data.session_id;
          localStorage.setItem('jarvis_session_id', currentSessionId);
        }
        if (Array.isArray(data.messages) && data.messages.length > 0) {
          messagesList.innerHTML = '';
          data.messages.forEach(m => {
            appendMessage(m.role === 'assistant' ? 'jarvis' : m.role, m.content);
          });
        } else if (messagesList.children.length === 0) {
          appendMessage('jarvis', data.message || 'JARVIS online and standing by, sir.');
          enqueueSentence(data.message || 'JARVIS online and standing by, sir.');
        }
      }
    } else if (data.type === 'sessions_list') {
      const activeSid = data.session_id || data.current_session_id || currentSessionId;
      if (activeSid) {
        currentSessionId = activeSid;
        localStorage.setItem('jarvis_session_id', currentSessionId);
      }
      renderSessionsList(data.sessions || [], currentSessionId);
    } else if (data.type === 'session_switched' || data.type === 'session_created' || data.type === 'session_deleted') {
      if (data.session_id) {
        currentSessionId = data.session_id;
        localStorage.setItem('jarvis_session_id', currentSessionId);
      }
      if (Array.isArray(data.sessions)) {
        renderSessionsList(data.sessions, currentSessionId);
      }
      messagesList.innerHTML = '';
      if (Array.isArray(data.messages) && data.messages.length > 0) {
        data.messages.forEach(m => {
          appendMessage(m.role === 'assistant' ? 'jarvis' : m.role, m.content);
        });
      } else {
        appendMessage('jarvis', 'JARVIS online and standing by, sir.');
      }
      if (userInput) userInput.focus();
      if (sessionsDrawer && data.type !== 'session_deleted') sessionsDrawer.classList.add('hidden');
    } else if (data.type === 'chunk') {
      resetThinkingTimeout();
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
      hideActiveToolBanner();
      statusText.textContent = 'Connected';
      const respText = data.text || 'Command completed, sir.';

      if (currentStreamingBubble) {
        currentStreamingBubble.innerHTML = renderMarkdown(respText);
      } else {
        appendMessage('jarvis', respText, { toolCalls: data.tool_calls });
      }

      if (!data.sound) {
        playStarkChime('done');
      }

      const hasStreamed = streamingFullText.length > 0;
      if (hasStreamed) {
        const tailText = streamingFullText.slice(lastProcessedIndex);
        if (tailText) enqueueSentence(tailText);
      } else if (!sentenceQueue.length && !isSpeaking) {
        enqueueSentence(respText);
      }

      currentStreamingBubble = null;
      streamingFullText = '';
      lastProcessedIndex = 0;
    } else if (data.type === 'diff_view') {
      clearThinkingTimeout();
      hideActiveToolBanner();
      statusText.textContent = 'Connected';
      renderDiffViewer(data.diff, data.stat, data.path);
    } else if (data.type === 'proactive_alert') {
      clearThinkingTimeout();
      playStarkChime('alert');
      const alertText = data.text || 'Proactive alert received.';
      appendMessage('jarvis', alertText, { isAlert: true });
      enqueueSentence(alertText);
    } else if (data.type === 'state_update') {
      const badge = document.createElement('div');
      badge.className = 'state-badge';
      badge.textContent = `// State Update [${data.domain} -> ${data.action}]`;
      messagesList.appendChild(badge);
      scrollToBottom();
      if (data.domain === 'directives') fetchDirectives();
      if (data.domain === 'missions') fetchMissions();
      if (data.domain === 'email') fetchDispatches();
    }
  }

  function sendMessage(text) {
    stopSpeech();
    clearThinkingTimeout();

    const clean = text.trim();
    if (!clean) return;

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      appendMessage('jarvis', 'Error: Backend is disconnected.', { isAlert: true });
      playStarkChime('alert');
      return;
    }

    appendMessage('user', clean);
    setOrbState('thinking');
    statusText.textContent = 'Processing';
    showActiveToolBanner('JARVIS is processing your request...');
    resetThinkingTimeout();

    if (clean.startsWith('/')) {
      ws.send(JSON.stringify({ type: 'slash_command', command: clean }));
    } else {
      ws.send(JSON.stringify({ type: 'message', message: clean }));
    }

    userInput.value = '';
    userInput.style.height = 'auto';
  }

  function sendImageMessage(base64Data, promptText) {
    stopSpeech();
    clearThinkingTimeout();

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      appendMessage('jarvis', 'Error: Backend is disconnected.', { isAlert: true });
      playStarkChime('alert');
      return;
    }

    appendMessage('user', `[Camera Vision Request] ${promptText || ''}`, { imageUrl: base64Data });
    setOrbState('thinking');
    statusText.textContent = 'Analyzing Vision';
    showActiveToolBanner('Multimodal Vision model inspecting camera image...');
    resetThinkingTimeout();

    ws.send(JSON.stringify({
      type: 'image_message',
      image_data: base64Data,
      prompt: promptText || 'Analyze this camera image in detail, sir.'
    }));

    userInput.value = '';
    userInput.style.height = 'auto';
  }

  // -------------------------------------------------------------
  // 7. VISUAL DIFF INSPECTOR
  // -------------------------------------------------------------
  function renderDiffViewer(diffText, statText, pathText) {
    currentRawDiff = diffText || '';
    if (diffPathText) diffPathText.textContent = pathText || 'Workspace: D:\\JARVIS';

    // Calculate additions & deletions if not provided
    if (diffStatBadge) {
      if (statText && statText.includes('insertion') || statText.includes('+')) {
        diffStatBadge.textContent = statText.split('\n').pop() || '+0 -0';
      } else {
        const adds = (diffText.match(/^\+[^+]/gm) || []).length;
        const dels = (diffText.match(/^-[^-]/gm) || []).length;
        diffStatBadge.textContent = `+${adds} -${dels}`;
      }
    }

    if (diffModalCode) {
      diffModalCode.innerHTML = '';
      if (!diffText || !diffText.trim()) {
        diffModalCode.innerHTML = '<span class="diff-line meta">No uncommitted changes detected. Working tree clean.</span>';
      } else {
        const lines = diffText.split('\n');
        lines.forEach(line => {
          const span = document.createElement('span');
          span.className = 'diff-line';
          if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('diff --git')) {
            span.classList.add('meta');
          } else if (line.startsWith('@@')) {
            span.classList.add('hunk');
          } else if (line.startsWith('+')) {
            span.classList.add('add');
          } else if (line.startsWith('-')) {
            span.classList.add('del');
          }
          span.textContent = line + '\n';
          diffModalCode.appendChild(span);
        });
      }
    }

    if (diffModal) diffModal.classList.remove('hidden');
    playStarkChime('ack');
  }

  async function openWorkspaceDiff() {
    try {
      const host = getWsHost();
      const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
      const res = await fetch(`${httpProto}://${host}/workspace/diff`);
      if (res.ok) {
        const data = await res.json();
        renderDiffViewer(data.diff, data.stat, data.path);
      } else if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'slash_command', command: '/diff' }));
      }
    } catch (err) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'slash_command', command: '/diff' }));
      }
    }
  }

  // -------------------------------------------------------------
  // 8. STARK COMMAND DECK (DIRECTIVES, DISPATCHES & MISSIONS)
  // -------------------------------------------------------------
  function switchDeckTab(tabName) {
    currentDeckTab = tabName;

    [tabDirectivesBtn, tabDispatchesBtn, tabMissionsBtn].forEach(btn => btn && btn.classList.remove('active'));
    [paneDirectives, paneDispatches, paneMissions].forEach(pane => pane && pane.classList.add('hidden'));

    if (tabName === 'directives') {
      if (tabDirectivesBtn) tabDirectivesBtn.classList.add('active');
      if (paneDirectives) paneDirectives.classList.remove('hidden');
      fetchDirectives();
    } else if (tabName === 'dispatches') {
      if (tabDispatchesBtn) tabDispatchesBtn.classList.add('active');
      if (paneDispatches) paneDispatches.classList.remove('hidden');
      fetchDispatches();
    } else if (tabName === 'missions') {
      if (tabMissionsBtn) tabMissionsBtn.classList.add('active');
      if (paneMissions) paneMissions.classList.remove('hidden');
      fetchMissions();
    }
  }

  // Pane 1: Directives Logic
  async function fetchDirectives() {
    if (!directivesContainer) return;
    try {
      const host = getWsHost();
      const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
      const res = await fetch(`${httpProto}://${host}/directives`);
      if (res.ok) {
        const directives = await res.json();
        renderDirectives(directives);
      }
    } catch (err) {
      directivesContainer.innerHTML = '<div class="loading-placeholder">Failed to sync directives.</div>';
    }
  }

  function renderDirectives(directives) {
    if (!directivesContainer) return;
    directivesContainer.innerHTML = '';

    if (!Array.isArray(directives) || directives.length === 0) {
      directivesContainer.innerHTML = '<div class="loading-placeholder">No active directives or calendar tasks found.</div>';
      return;
    }

    directives.forEach(d => {
      const item = document.createElement('div');
      item.className = `directive-item ${d.completed ? 'completed' : ''}`;

      const check = document.createElement('input');
      check.type = 'checkbox';
      check.className = 'directive-check';
      check.checked = !!d.completed;
      check.disabled = String(d.id).startsWith('cal_');

      check.addEventListener('change', async () => {
        try {
          const host = getWsHost();
          const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
          await fetch(`${httpProto}://${host}/directives/${d.id}/complete`, { method: 'POST' });
          item.classList.toggle('completed', check.checked);
        } catch (e) {}
      });

      const info = document.createElement('div');
      info.className = 'directive-info';
      info.innerHTML = `
        <div class="directive-title">${d.text || d.title || 'Untitled Directive'}</div>
        <div class="directive-meta">
          <span class="directive-src-pill">${d.source === 'calendar' ? 'CALENDAR' : 'DIRECTIVE'}</span>
          <span>${d.created_at || d.date || ''}</span>
        </div>
      `;

      const delBtn = document.createElement('button');
      delBtn.className = 'directive-delete-btn';
      delBtn.innerHTML = '✕';
      delBtn.title = 'Delete Directive';
      if (String(d.id).startsWith('cal_')) delBtn.style.display = 'none';

      delBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        try {
          const host = getWsHost();
          const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
          await fetch(`${httpProto}://${host}/directives/${d.id}`, { method: 'DELETE' });
          item.remove();
        } catch (e) {}
      });

      item.appendChild(check);
      item.appendChild(info);
      item.appendChild(delBtn);
      directivesContainer.appendChild(item);
    });
  }

  async function createDirective() {
    if (!newDirectiveInput) return;
    const text = newDirectiveInput.value.trim();
    if (!text) return;
    newDirectiveInput.value = '';

    try {
      const host = getWsHost();
      const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
      await fetch(`${httpProto}://${host}/directives`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      playStarkChime('ack');
      fetchDirectives();
    } catch (e) {}
  }

  // Pane 2: Dispatches Logic
  async function fetchDispatches() {
    if (!dispatchesContainer) return;
    try {
      const host = getWsHost();
      const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
      const endpoint = emailDeckMode === 'sent' ? `${httpProto}://${host}/email/sent` : `${httpProto}://${host}/directives`;
      const res = await fetch(endpoint);
      if (res.ok) {
        const data = await res.json();
        const emails = emailDeckMode === 'sent' ? (data.sent_emails || []) : (data.emails || []);
        renderDispatches(emails);
      }
    } catch (e) {
      dispatchesContainer.innerHTML = '<div class="loading-placeholder">No dispatches available offline.</div>';
    }
  }

  function renderDispatches(emails) {
    if (!dispatchesContainer) return;
    dispatchesContainer.innerHTML = '';

    if (!Array.isArray(emails) || emails.length === 0) {
      dispatchesContainer.innerHTML = `
        <div class="loading-placeholder">
          No ${emailDeckMode} dispatches found.<br>
          <small>Ask JARVIS to "check my email" to fetch live Gmail cards.</small>
        </div>
      `;
      return;
    }

    emails.forEach(mail => {
      const card = document.createElement('div');
      card.className = 'dispatch-card';
      card.innerHTML = `
        <div class="dispatch-header">
          <span class="dispatch-from">${mail.from || mail.to || 'Unknown'}</span>
          <span class="dispatch-date">${mail.date || ''}</span>
        </div>
        <div class="dispatch-subject">${mail.subject || 'No Subject'}</div>
        ${mail.snippet ? `<div class="dispatch-snippet">${mail.snippet}</div>` : ''}
      `;
      dispatchesContainer.appendChild(card);
    });
  }

  // Pane 3: Autonomous Missions Logic
  async function fetchMissions() {
    if (!missionsContainer) return;
    try {
      const host = getWsHost();
      const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
      const res = await fetch(`${httpProto}://${host}/missions`);
      if (res.ok) {
        const missions = await res.json();
        renderMissions(missions);
      }
    } catch (e) {
      missionsContainer.innerHTML = '<div class="loading-placeholder">Failed to load missions.</div>';
    }
  }

  function renderMissions(missions) {
    if (!missionsContainer) return;
    missionsContainer.innerHTML = '';

    if (!Array.isArray(missions) || missions.length === 0) {
      missionsContainer.innerHTML = `
        <div class="loading-placeholder">
          No autonomous missions active.<br>
          <small>Type "/goal [goal]" or propose high-level objectives to activate.</small>
        </div>
      `;
      return;
    }

    missions.forEach(m => {
      const card = document.createElement('div');
      card.className = 'mission-card';
      const pct = m.progress_percentage || 0;

      card.innerHTML = `
        <div class="mission-card-header">
          <span class="mission-id">#${m.id}</span>
          <span class="mission-status-pill ${m.status}">${m.status}</span>
        </div>
        <div class="mission-title">${m.title || 'Autonomous Mission'}</div>
        <div class="mission-objective">${m.objective || ''}</div>
        <div class="mission-progress-bar">
          <div class="mission-progress-fill" style="width: ${pct}%;"></div>
        </div>
        <div class="mission-stats-row">
          <span>PROGRESS: ${pct}%</span>
          <span>${m.completed_task_count || 0}/${m.task_count || 0} TASKS</span>
        </div>
        <div class="mission-actions-row">
          <button class="mission-action-btn" data-act="resume">▶ RESUME</button>
          <button class="mission-action-btn" data-act="pause">⏸ PAUSE</button>
          <button class="mission-action-btn" data-act="approve">✓ APPROVE</button>
          <button class="mission-action-btn" data-act="cancel">✕ CANCEL</button>
        </div>
      `;

      card.querySelectorAll('.mission-action-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
          const action = btn.dataset.act;
          try {
            const host = getWsHost();
            const httpProto = window.location.protocol.startsWith('https') ? 'https' : 'http';
            await fetch(`${httpProto}://${host}/missions/${m.id}/${action}`, { method: 'POST' });
            playStarkChime('ack');
            fetchMissions();
          } catch (e) {}
        });
      });

      missionsContainer.appendChild(card);
    });
  }

  // -------------------------------------------------------------
  // 9. SPEECH RECOGNITION & MOBILE TOUCH LISTENERS
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

  // Mobile Keyboard Ergonomics: Auto-collapse orb when input is focused
  userInput.addEventListener('focus', () => {
    toggleOrbCollapse(true);
  });

  // Auto-collapse orb when user scrolls chat down
  chatContainer.addEventListener('scroll', () => {
    if (chatContainer.scrollTop > 60 && !isOrbCollapsed) {
      toggleOrbCollapse(true);
    } else if (chatContainer.scrollTop <= 10 && isOrbCollapsed && document.activeElement !== userInput) {
      toggleOrbCollapse(false);
    }
  });

  if (orbToggleBtn) {
    orbToggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleOrbCollapse();
    });
  }

  micBtn.addEventListener('click', () => {
    if (!recognition) return;
    if (isListening) recognition.stop();
    else recognition.start();
  });

  actionPills.addEventListener('click', (e) => {
    const pill = e.target.closest('.pill-btn');
    if (!pill) return;
    if (pill.id === 'deckMissionsPill') {
      commandDeckDrawer.classList.remove('hidden');
      switchDeckTab('missions');
      return;
    }
    if (pill.dataset.cmd === '/diff') {
      openWorkspaceDiff();
      return;
    }
    if (pill.dataset.cmd) sendMessage(pill.dataset.cmd);
  });

  // Persona Switcher Listeners
  if (personaBadgeBtn) {
    personaBadgeBtn.addEventListener('click', () => {
      renderPersonaGrid();
      personaModal.classList.remove('hidden');
    });
  }
  if (closePersonaBtn) {
    closePersonaBtn.addEventListener('click', () => personaModal.classList.add('hidden'));
  }

  // Command Deck Listeners
  if (deckToggleBtn) {
    deckToggleBtn.addEventListener('click', () => {
      commandDeckDrawer.classList.remove('hidden');
      switchDeckTab(currentDeckTab);
    });
  }
  if (closeDeckBtn) {
    closeDeckBtn.addEventListener('click', () => commandDeckDrawer.classList.add('hidden'));
  }
  if (tabDirectivesBtn) tabDirectivesBtn.addEventListener('click', () => switchDeckTab('directives'));
  if (tabDispatchesBtn) tabDispatchesBtn.addEventListener('click', () => switchDeckTab('dispatches'));
  if (tabMissionsBtn) tabMissionsBtn.addEventListener('click', () => switchDeckTab('missions'));

  if (addDirectiveBtn) addDirectiveBtn.addEventListener('click', createDirective);
  if (newDirectiveInput) {
    newDirectiveInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') createDirective();
    });
  }
  if (refreshDirectivesBtn) refreshDirectivesBtn.addEventListener('click', fetchDirectives);

  if (dispInboxBtn) {
    dispInboxBtn.addEventListener('click', () => {
      emailDeckMode = 'inbox';
      dispInboxBtn.classList.add('active');
      dispSentBtn.classList.remove('active');
      fetchDispatches();
    });
  }
  if (dispSentBtn) {
    dispSentBtn.addEventListener('click', () => {
      emailDeckMode = 'sent';
      dispSentBtn.classList.add('active');
      dispInboxBtn.classList.remove('active');
      fetchDispatches();
    });
  }
  if (refreshDispatchesBtn) refreshDispatchesBtn.addEventListener('click', fetchDispatches);
  if (refreshMissionsBtn) refreshMissionsBtn.addEventListener('click', fetchMissions);

  commandDeckDrawer.addEventListener('click', (e) => {
    const card = e.target.closest('.protocol-card');
    if (card && card.dataset.cmd) {
      commandDeckDrawer.classList.add('hidden');
      sendMessage(card.dataset.cmd);
    }
  });

  // Diff Modal Listeners
  if (closeDiffBtn) closeDiffBtn.addEventListener('click', () => diffModal.classList.add('hidden'));
  if (copyDiffBtn) {
    copyDiffBtn.addEventListener('click', () => {
      if (currentRawDiff) {
        navigator.clipboard.writeText(currentRawDiff);
        copyDiffBtn.textContent = 'COPIED';
        setTimeout(() => { copyDiffBtn.textContent = 'COPY'; }, 1500);
      }
    });
  }
  if (refreshDiffBtn) refreshDiffBtn.addEventListener('click', openWorkspaceDiff);

  // Camera & Vision Handlers
  if (mobileCameraBtn) {
    mobileCameraBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (mobileCameraInput) mobileCameraInput.click();
    });
  }
  if (mobileInputCamBtn) {
    mobileInputCamBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (mobileCameraInput) mobileCameraInput.click();
    });
  }
  if (mobileCameraInput) {
    mobileCameraInput.addEventListener('change', () => {
      const file = mobileCameraInput.files && mobileCameraInput.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (e) => {
        const base64Data = e.target.result;
        sendImageMessage(base64Data, userInput.value.trim() || 'Analyze this camera image in detail, sir.');
        mobileCameraInput.value = '';
      };
      reader.readAsDataURL(file);
    });
  }

  // Hands-Free Toggle Handler
  if (mobileHandsFreeBtn) {
    mobileHandsFreeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const nextState = !isHandsFreeActive;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'handsfree', action: nextState ? 'start' : 'stop' }));
      }
      isHandsFreeActive = nextState;
      if (isHandsFreeActive) {
        mobileHandsFreeBtn.classList.add('active');
        mobileHandsFreeBtn.textContent = 'Hands-Free ON';
        playStarkChime('wake');
      } else {
        mobileHandsFreeBtn.classList.remove('active');
        mobileHandsFreeBtn.textContent = 'Hands-Free';
        playStarkChime('ack');
      }
    });
  }

  // Tap-to-Barge-In Handlers
  if (orbCanvas) {
    orbCanvas.addEventListener('click', () => {
      if (isSpeaking) {
        stopSpeech();
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'barge_in' }));
        }
      }
    });
  }

  if (chatContainer) {
    chatContainer.addEventListener('click', (e) => {
      if (e.target.closest('button') || e.target.closest('a') || e.target.closest('input')) return;
      if (isSpeaking) {
        stopSpeech();
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'barge_in' }));
        }
      }
    });
  }

  // Sessions Drawer Handlers
  function renderSessionsList(sessions, activeId) {
    if (!sessionsList) return;
    sessionsList.innerHTML = '';
    if (!sessions || sessions.length === 0) {
      sessionsList.innerHTML = '<div style="color: var(--text-muted); font-size: 0.75rem; font-style: italic;">No past sessions found</div>';
      return;
    }

    sessions.forEach(s => {
      const card = document.createElement('div');
      card.className = `session-card ${s.session_id === (activeId || currentSessionId) ? 'active' : ''}`;

      const headerRow = document.createElement('div');
      headerRow.style.display = 'flex';
      headerRow.style.justifyContent = 'space-between';
      headerRow.style.alignItems = 'center';
      headerRow.style.width = '100%';

      const title = document.createElement('div');
      title.className = 'session-title-text';
      title.textContent = s.title || 'Untitled Session';

      const delBtn = document.createElement('button');
      delBtn.className = 'session-delete-btn';
      delBtn.innerHTML = 'DEL';
      delBtn.title = 'Delete session';
      delBtn.style.background = 'transparent';
      delBtn.style.border = 'none';
      delBtn.style.color = 'var(--text-muted)';
      delBtn.style.fontSize = '0.75rem';
      delBtn.style.padding = '2px 4px';
      delBtn.style.cursor = 'pointer';
      delBtn.style.borderRadius = '4px';

      // Inline touch-friendly delete confirmation without blocking confirm()
      delBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (delBtn.dataset.confirming === 'true') {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'delete_session', session_id: s.session_id }));
          }
          card.remove();
        } else {
          delBtn.dataset.confirming = 'true';
          delBtn.textContent = 'SURE?';
          delBtn.style.color = '#ff1744';
          setTimeout(() => {
            delBtn.dataset.confirming = 'false';
            delBtn.textContent = 'DEL';
            delBtn.style.color = 'var(--text-muted)';
          }, 3000);
        }
      });

      headerRow.appendChild(title);
      headerRow.appendChild(delBtn);

      const meta = document.createElement('div');
      meta.className = 'session-meta-text';
      const la = s.last_active;
      const dateStr = la ? new Date(typeof la === 'number' && la < 1e11 ? la * 1000 : la).toLocaleDateString([], { month: 'short', day: 'numeric' }) : 'Recent';
      meta.textContent = `${dateStr} · ${s.message_count || 0} msgs`;

      card.appendChild(headerRow);
      card.appendChild(meta);

      card.addEventListener('click', () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'switch_session', session_id: s.session_id }));
        }
      });

      sessionsList.appendChild(card);
    });
  }

  if (sessionsToggleBtn) {
    sessionsToggleBtn.addEventListener('click', () => {
      sessionsDrawer.classList.remove('hidden');
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'get_sessions' }));
      }
    });
  }
  if (closeSessionsBtn) closeSessionsBtn.addEventListener('click', () => sessionsDrawer.classList.add('hidden'));
  if (newSessionBtn) {
    newSessionBtn.addEventListener('click', () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'new_session' }));
      }
    });
  }

  // Settings Handlers
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

  // Mobile viewport adjustment for soft keyboard
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', () => {
      if (window.visualViewport.height < window.innerHeight * 0.75) {
        // Keyboard is likely open
        toggleOrbCollapse(true);
      }
    });
  }

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('sw.js').catch(() => {});
    });
  }

  // Launch App, Persona Registry & Visualizer
  initOrbVisualizer();
  initSpeechRecognition();
  fetchAgents();
  connectWebSocket();
})();
