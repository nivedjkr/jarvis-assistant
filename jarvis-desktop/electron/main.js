const { app, BrowserWindow, ipcMain } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const WebSocket = require('ws')
const http = require('http')

let mainWindow
let jarvisProcess
let ws

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

function startJarvisBackend() {
  const jarvisPath = 'D:\\JARVIS'
  
  jarvisProcess = spawn(
    'python', ['-m', 'jarvis.api'],
    {
      cwd: jarvisPath,
      env: { 
        ...process.env,
        PYTHONPATH: jarvisPath
      },
      shell: true
    }
  )
  
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
    console.error('[PYTHON] Failed to start:', err)
  })
  
  setTimeout(() => {
    if (!ws || ws.readyState !== 1) {
      console.log('[WS] Fallback connection attempt')
      connectWebSocket()
    }
  }, 5000)
}

function connectWebSocket() {
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
  if (jarvisProcess) {
    try { jarvisProcess.kill('SIGTERM') } catch (e) {}
  }
  app.quit()
})

app.on('will-quit', () => {
  if (jarvisProcess) {
    try { jarvisProcess.kill('SIGTERM') } catch (e) {}
  }
})

app.whenReady().then(() => {
  createWindow()
  startJarvisBackend()
})
