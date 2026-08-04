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
    backgroundColor: '#000000',
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
  const rootDir = path.resolve(__dirname, '..', '..')
  jarvisProcess = spawn('python', ['-m', 'jarvis.api'], {
    cwd: rootDir,
    env: { ...process.env }
  })
  
  jarvisProcess.on('error', (err) => {
    console.log('Backend spawn error:', err.message)
  })

  if (jarvisProcess.stdout) {
    jarvisProcess.stdout.on('data', (data) => {
      console.log('JARVIS:', data.toString())
    })
  }

  if (jarvisProcess.stderr) {
    jarvisProcess.stderr.on('data', (data) => {
      console.error('JARVIS STDERR:', data.toString())
    })
  }

  setTimeout(connectWebSocket, 2000)
}

function connectWebSocket() {
  try {
    ws = new WebSocket('ws://127.0.0.1:8765/ws')
    
    ws.on('open', () => {
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
      } catch (err) {
        console.log('WS parse error:', err.message)
      }
    })
    
    ws.on('close', () => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('connection-status', 'disconnected')
      }
      setTimeout(connectWebSocket, 3000)
    })

    ws.on('error', (err) => {
      console.log('WebSocket error (waiting for backend):', err.message)
    })
  } catch (err) {
    console.log('WebSocket init error:', err.message)
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

ipcMain.handle('get-projects', () => fetchJson('http://127.0.0.1:8765/projects'))
ipcMain.handle('get-reminders', () => fetchJson('http://127.0.0.1:8765/reminders'))
ipcMain.handle('get-watchlist', () => fetchJson('http://127.0.0.1:8765/watchlist'))

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
