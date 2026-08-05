const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('jarvis', {
  sendMessage: (text) => ipcRenderer.invoke('send-message', text),
  sendSlashCommand: (command) => ipcRenderer.invoke('send-slash-command', command),
  synthesizeSpeech: (text) => ipcRenderer.invoke('synthesize-speech', text),
  synthesizeSentence: (sentence) => ipcRenderer.invoke('jarvis:synthesizeSentence', sentence),
  onResponse: (cb) => {
    ipcRenderer.removeAllListeners('jarvis-response')
    ipcRenderer.on('jarvis-response', (_, data) => cb(data))
  },
  onStatus: (cb) => {
    ipcRenderer.removeAllListeners('connection-status')
    ipcRenderer.on('connection-status', (_, status) => cb(status))
  },
  getProjects: () => ipcRenderer.invoke('get-projects'),
  getReminders: () => ipcRenderer.invoke('get-reminders'),
  getWatchlist: () => ipcRenderer.invoke('get-watchlist'),
  getVitals: () => ipcRenderer.invoke('get-vitals'),

  minimize: () => ipcRenderer.invoke('window-minimize'),
  close: () => ipcRenderer.invoke('window-close')
})
