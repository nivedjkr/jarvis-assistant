const { app, BrowserWindow, ipcMain } = require('electron')
const { spawn, exec, execFile } = require('child_process')
const path = require('path')
const WebSocket = require('ws')
const http = require('http')
const net = require('net')
const fs = require('fs')

let mainWindow
let jarvisProcess
let ws
let backendFailed = false

function loadDotEnv(envPath) {
  if (fs.existsSync(envPath)) {
    try {
      const content = fs.readFileSync(envPath, 'utf8')
      for (const line of content.split('\n')) {
        const trimmed = line.trim()
        if (trimmed && !trimmed.startsWith('#') && trimmed.includes('=')) {
          const parts = trimmed.split('=')
          const key = parts[0].trim()
          const val = parts.slice(1).join('=').trim()
          if (key && !process.env[key]) {
            process.env[key] = val
          }
        }
      }
    } catch (e) {
      console.warn('[ELECTRON] Error parsing .env file:', e)
    }
  }
}

const rootEnvFile = path.resolve(__dirname, '..', '..', '.env')
loadDotEnv(rootEnvFile)

function checkPortInUse(port, host = '127.0.0.1') {
  return new Promise((resolve) => {
    const socket = new net.Socket()
    socket.setTimeout(1000)
    
    socket.on('connect', () => {
      socket.destroy()
      resolve(true)
    })
    
    socket.on('timeout', () => {
      socket.destroy()
      resolve(false)
    })
    
    socket.on('error', () => {
      resolve(false)
    })
    
    socket.connect(port, host)
  })
}

function freePort8765() {
  return new Promise((resolve) => {
    if (process.platform === 'win32') {
      const psCmd = 'Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }'
      execFile('powershell.exe', ['-NoProfile', '-Command', psCmd], () => {
        const cmd = `cmd /c "for /f \\"tokens=5\\" %a in ('netstat -aon ^| findstr :8765 ^| findstr LISTENING') do taskkill /F /PID %a"`
        exec(cmd, (err, stdout) => {
          if (stdout && stdout.trim()) {
            console.log('[ELECTRON] Freed port 8765:', stdout.trim())
          }
          resolve()
        })
      })
    } else {
      exec(`lsof -ti :8765 | xargs kill -9`, () => resolve())
    }
  })
}

async function ensurePortFree(port = 8765) {
  let isOccupied = await checkPortInUse(port)
  if (!isOccupied) return true

  console.warn(`[ELECTRON] Port ${port} is currently in use. Freeing port...`)
  await freePort8765()

  for (let attempt = 1; attempt <= 10; attempt++) {
    await new Promise(r => setTimeout(r, 300))
    isOccupied = await checkPortInUse(port)
    if (!isOccupied) {
      console.log(`[ELECTRON] Port ${port} successfully freed on attempt ${attempt}.`)
      return true
    }
  }

  console.error(`[ELECTRON] Warning: Port ${port} is still in use after port cleanup attempts.`)
  return false
}

function killBackendProcess() {
  if (jarvisProcess && jarvisProcess.pid) {
    const pid = jarvisProcess.pid
    console.log(`[ELECTRON] Killing backend process tree (PID: ${pid})...`)
    if (process.platform === 'win32') {
      try {
        exec(`taskkill /pid ${pid} /T /F`, (err) => {
          if (err) console.log('[ELECTRON] taskkill info:', err.message)
        })
      } catch (e) {
        console.error('[ELECTRON] Error executing taskkill:', e)
      }
    } else {
      try {
        jarvisProcess.kill('SIGTERM')
      } catch (e) {}
    }
    jarvisProcess = null
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1080,
    height: 720,
    backgroundColor: '#08080b',
    frame: false,

    titleBarStyle: 'hidden',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })
  
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

function getPythonExecutable(jarvisPath) {
  if (process.env.PYTHON_PATH && fs.existsSync(process.env.PYTHON_PATH)) {
    console.log('[ELECTRON] Using PYTHON_PATH from env:', process.env.PYTHON_PATH)
    return process.env.PYTHON_PATH
  }

  const isWin = process.platform === 'win32'

  // 1. Check local virtual environments first (venv or .venv)
  const venvPaths = isWin
    ? [
        path.join(jarvisPath, 'venv', 'Scripts', 'python.exe'),
        path.join(jarvisPath, '.venv', 'Scripts', 'python.exe')
      ]
    : [
        path.join(jarvisPath, 'venv', 'bin', 'python'),
        path.join(jarvisPath, '.venv', 'bin', 'python')
      ]

  for (const p of venvPaths) {
    if (fs.existsSync(p)) {
      console.log('[ELECTRON] Found Python virtual environment:', p)
      return p
    }
  }

  // 2. On Windows, avoid WindowsApps redirector alias (which exits with code 1)
  if (isWin) {
    const knownWinPaths = [
      'C:\\msys64\\ucrt64\\bin\\python.exe',
      'C:\\Python311\\python.exe',
      'C:\\Python310\\python.exe',
      path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe'),
      path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python310', 'python.exe')
    ]
    for (const candidate of knownWinPaths) {
      if (candidate && fs.existsSync(candidate)) {
        console.log('[ELECTRON] Found Windows Python installation:', candidate)
        return candidate
      }
    }
  }

  const defaultCmd = isWin ? 'python' : 'python3'
  console.log('[ELECTRON] Using default system command:', defaultCmd)
  return defaultCmd
}

async function startJarvisBackend() {
  const defaultPath = path.resolve(__dirname, '..', '..')
  const jarvisPath = process.env.JARVIS_BACKEND_PATH || defaultPath
  console.log('[ELECTRON] Resolving JARVIS backend path:', jarvisPath)
  
  if (!fs.existsSync(jarvisPath)) {
    const errorMsg = `JARVIS backend path directory does not exist: ${jarvisPath}`
    console.error('[PYTHON ERROR]', errorMsg)
    backendFailed = true
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('connection-status', 'disconnected')
      mainWindow.webContents.send('jarvis-response', {
        type: 'response',
        text: `Error: ${errorMsg}`
      })
    }
    return
  }

  // Pre-spawn check: clear orphaned processes bound to port 8765 and wait until port is free
  await ensurePortFree(8765)
  
  const pythonBin = getPythonExecutable(jarvisPath)
  console.log(`[ELECTRON] Spawning Python backend with executable: ${pythonBin}`)

  // Spawn Python backend directly without shell wrapper for clean PID tracking
  jarvisProcess = spawn(
    pythonBin, ['-m', 'jarvis.api'],
    {
      cwd: jarvisPath,
      env: { 
        ...process.env,
        PYTHONPATH: jarvisPath,
        PYTHONUNBUFFERED: '1',
        OPENBLAS_NUM_THREADS: '1',
        MKL_NUM_THREADS: '1',
        NUMEXPR_NUM_THREADS: '1',
        OMP_NUM_THREADS: '1'
      },
      shell: false
    }
  )

  console.log(`[ELECTRON] Python backend spawned with PID ${jarvisProcess.pid}`)
  
  let wsConnecting = false
  const handleServerOutput = (text) => {
    if (wsConnecting) return
    if (text.includes('Uvicorn running on http://') || text.includes('Uvicorn running')) {
      wsConnecting = true
      console.log('[WS] Server ready, connecting...')
      connectWebSocket()
    }
  }

  if (jarvisProcess.stdout) {
    jarvisProcess.stdout.on('data', (data) => {
      const text = data.toString()
      console.log('[PYTHON]', text)
      handleServerOutput(text)
    })
  }
  
  if (jarvisProcess.stderr) {
    jarvisProcess.stderr.on('data', (data) => {
      const text = data.toString()
      console.log('[PYTHON ERR]', text)
      handleServerOutput(text)
    })
  }
  
  jarvisProcess.on('error', (err) => {
    console.error('[PYTHON PROCESS ERROR] Failed to start:', err.message)
    backendFailed = true
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('connection-status', 'disconnected')
      mainWindow.webContents.send('jarvis-response', {
        type: 'response',
        text: `Failed to launch Python backend process: ${err.message}`
      })
    }
  })

  jarvisProcess.on('exit', (code, signal) => {
    if (code !== 0 && code !== null) {
      console.error(`[PYTHON PROCESS EXIT] Backend exited with code ${code}, signal ${signal}`)
      backendFailed = true
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('connection-status', 'disconnected')
        mainWindow.webContents.send('jarvis-response', {
          type: 'response',
          text: `JARVIS backend process exited with code ${code}. Check terminal/console for error log.`
        })
      }
    }
  })
  
  setTimeout(() => {
    if (!ws || ws.readyState !== 1) {
      if (!backendFailed) {
        console.log('[WS] Fallback connection attempt')
        connectWebSocket()
      } else {
        console.warn('[WS] Skipping fallback connection: Backend failed to start.')
      }
    }
  }, 5000)
}

function getOrCreateSessionId() {
  try {
    const sessionFile = path.join(app.getPath('userData'), 'session_config.json')
    if (fs.existsSync(sessionFile)) {
      const data = JSON.parse(fs.readFileSync(sessionFile, 'utf8'))
      if (data.session_id) return data.session_id
    }
    const newId = 'electron_' + Math.random().toString(36).substring(2, 10)
    fs.writeFileSync(sessionFile, JSON.stringify({ session_id: newId }))
    return newId
  } catch (e) {
    return 'electron_default'
  }
}

function connectWebSocket() {
  if (backendFailed) {
    console.warn('[WS] Backend process failed. Skipping WebSocket connection retry.')
    return
  }
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return
  }
  try {
    loadDotEnv(rootEnvFile)
    const wsToken = process.env.JARVIS_WS_TOKEN || 'jarvis_secure_local_token_2026'
    const sessionId = getOrCreateSessionId()
    ws = new WebSocket(`ws://127.0.0.1:8765/ws?token=${wsToken}&session_id=${sessionId}`)
    
    ws.on('open', () => {
      console.log('[WS] Connected to JARVIS backend')
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('connection-status', 'connected')
      }
    })
    
    ws.on('message', (data) => {
      try {
        const parsed = JSON.parse(data)
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('jarvis-response', parsed)
        }
      } catch (e) {
        console.error('[WS] Parse error:', e)
      }
    })
    
    ws.on('error', (err) => {
      console.error('[WS] Error:', err.message)
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('connection-status', 'disconnected')
      }
    })
    
    ws.on('close', () => {
      if (backendFailed) {
        console.warn('[WS] Connection closed. Not retrying since backend failed.')
        return
      }
      console.log('[WS] Disconnected — retrying in 3s')
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('connection-status', 'disconnected')
      }
      setTimeout(connectWebSocket, 3000)
    })
  } catch (e) {
    console.error('[WS] Init error:', e)
  }
}

function fetchJson(url) {
  return new Promise((resolve) => {
    http.get(url, (res) => {
      let data = ''
      res.on('data', chunk => data += chunk)
      res.on('end', () => {
        try {
          resolve(JSON.parse(data))
        } catch {
          resolve([])
        }
      })
    }).on('error', () => resolve([]))
  })
}

// IPC Handlers
ipcMain.handle('send-message', (event, text) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'message', message: text }))
  } else {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('jarvis-response', {
        type: 'response',
        text: 'JARVIS backend is offline or reconnecting, sir. Please try again shortly.'
      })
    }
  }
})

ipcMain.handle('send-slash-command', (event, command) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'slash_command', command: command }))
  } else {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('jarvis-response', {
        type: 'response',
        text: 'JARVIS backend is offline or reconnecting, sir. Please try again shortly.'
      })
    }
  }
})

ipcMain.handle('get-sessions', () => fetchJson('http://127.0.0.1:8765/sessions'))

ipcMain.handle('switch-session', (event, sid) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'switch_session', session_id: sid }))
  }
})

ipcMain.handle('new-session', () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'new_session' }))
  }
})

ipcMain.handle('rename-session', (event, payload) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'rename_session', session_id: payload?.session_id, title: payload?.title }))
  }
})

ipcMain.handle('delete-session', (event, sid) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'delete_session', session_id: sid }))
  }
})

ipcMain.handle('synthesize-speech', (event, text) => {
  return new Promise((resolve) => {
    if (!text || typeof text !== 'string') {
      return resolve('')
    }
    const postData = JSON.stringify({ text })
    const req = http.request({
      hostname: '127.0.0.1',
      port: 8765,
      path: '/tts',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      }
    }, (res) => {
      let data = ''
      res.on('data', chunk => data += chunk)
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data)
          resolve(parsed.audio || '')
        } catch {
          resolve('')
        }
      })
    })
    req.on('error', (err) => {
      console.log('TTS request error:', err.message)
      resolve('')
    })
    req.write(postData)
    req.end()
  })
})

const handleSynthesizeSentence = (event, sentence) => {
  return new Promise((resolve) => {
    if (!sentence || typeof sentence !== 'string') {
      return resolve('')
    }
    const postData = JSON.stringify({ sentence })
    const req = http.request({
      hostname: '127.0.0.1',
      port: 8765,
      path: '/tts_sentence',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      }
    }, (res) => {
      let data = ''
      res.on('data', chunk => data += chunk)
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data)
          resolve(parsed.audio || '')
        } catch {
          resolve('')
        }
      })
    })
    req.on('error', (err) => {
      console.log('TTS sentence request error:', err.message)
      resolve('')
    })
    req.write(postData)
    req.end()
  })
}

ipcMain.handle('jarvis:synthesizeSentence', handleSynthesizeSentence)
ipcMain.handle('synthesize-sentence', handleSynthesizeSentence)

ipcMain.handle('get-projects', () => fetchJson('http://127.0.0.1:8765/projects'))
ipcMain.handle('get-reminders', () => fetchJson('http://127.0.0.1:8765/reminders'))
ipcMain.handle('get-watchlist', () => fetchJson('http://127.0.0.1:8765/watchlist'))
ipcMain.handle('get-vitals', () => fetchJson('http://127.0.0.1:8765/vitals'))
ipcMain.handle('get-sessions', () => fetchJson('http://127.0.0.1:8765/sessions'))

ipcMain.handle('switch-session', (event, sessionId) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'switch_session', session_id: sessionId }))
  }
})

ipcMain.handle('new-session', () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'new_session' }))
  }
})

ipcMain.handle('rename-session', (event, { session_id, title }) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'rename_session', session_id, title }))
  }
})

ipcMain.handle('delete-session', (event, sessionId) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'delete_session', session_id: sessionId }))
  }
})

ipcMain.handle('check-email', () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'slash_command', command: '/email' }))
  }
})


ipcMain.handle('get-calendar-events', () => fetchJson('http://127.0.0.1:8765/calendar/events'))

ipcMain.handle('toggle-fullscreen', () => {
  if (mainWindow) {
    const isFS = mainWindow.isFullScreen()
    mainWindow.setFullScreen(!isFS)
    return !isFS
  }
  return false
})

ipcMain.handle('window-minimize', () => mainWindow && mainWindow.minimize())
ipcMain.handle('window-close', () => {
  killBackendProcess()
  app.quit()
})

app.on('will-quit', () => {
  killBackendProcess()
})

app.whenReady().then(() => {
  createWindow()
  startJarvisBackend()
})
