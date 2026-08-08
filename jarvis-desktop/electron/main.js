const { app, BrowserWindow, ipcMain } = require('electron')
const { spawn, exec } = require('child_process')
const path = require('path')
const WebSocket = require('ws')
const http = require('http')
const net = require('net')
const fs = require('fs')

let mainWindow
let jarvisProcess
let ws
let backendFailed = false

function checkPortInUse(port, host = '127.0.0.1') {
  return new Promise((resolve) => {
    const socket = new net.Socket()
    socket.setTimeout(400)
    
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
      const cmd = `cmd /c "for /f \\"tokens=5\\" %a in ('netstat -aon ^| findstr :8765 ^| findstr LISTENING') do taskkill /F /PID %a"`
      exec(cmd, (err, stdout) => {
        if (stdout && stdout.trim()) {
          console.log('[ELECTRON] Freed port 8765:', stdout.trim())
        }
        resolve()
      })
    } else {
      exec(`lsof -ti :8765 | xargs kill -9`, () => resolve())
    }
  })
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

  // Pre-spawn check: clear orphaned processes bound to port 8765
  const portOccupied = await checkPortInUse(8765)
  if (portOccupied) {
    console.warn('[ELECTRON] Port 8765 is in use by an orphaned process. Freeing port...')
    await freePort8765()
    await new Promise(r => setTimeout(r, 600))
  }
  
  // Spawn Python backend directly without shell wrapper for clean PID tracking
  jarvisProcess = spawn(
    'python', ['-m', 'jarvis.api'],
    {
      cwd: jarvisPath,
      env: { 
        ...process.env,
        PYTHONPATH: jarvisPath
      },
      shell: false
    }
  )

  console.log(`[ELECTRON] Python backend spawned with PID ${jarvisProcess.pid}`)
  
  if (jarvisProcess.stdout) {
    jarvisProcess.stdout.on('data', (data) => {
      const text = data.toString()
      console.log('[PYTHON]', text)
      if (text.includes('Uvicorn running') || text.includes('Application startup')) {
        console.log('[WS] Server ready, connecting...')
        connectWebSocket()
      }
    })
  }
  
  if (jarvisProcess.stderr) {
    jarvisProcess.stderr.on('data', (data) => {
      const text = data.toString()
      console.log('[PYTHON ERR]', text)
      if (text.includes('Uvicorn running') || text.includes('Application startup')) {
        console.log('[WS] Server ready, connecting...')
        connectWebSocket()
      }
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

function connectWebSocket() {
  if (backendFailed) {
    console.warn('[WS] Backend process failed. Skipping WebSocket connection retry.')
    return
  }
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return
  }
  try {
    ws = new WebSocket('ws://127.0.0.1:8765/ws')
    
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
