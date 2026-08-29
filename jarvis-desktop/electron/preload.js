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
  createProject: (name, path = '') => ipcRenderer.invoke('create-project', { name, path }),
  deleteProject: (projectId) => ipcRenderer.invoke('delete-project', projectId),
  getReminders: () => ipcRenderer.invoke('get-directives'),
  getDirectives: () => ipcRenderer.invoke('get-directives'),
  completeDirective: (directiveId) => ipcRenderer.invoke('complete-directive', directiveId),
  deleteDirective: (directiveId) => ipcRenderer.invoke('delete-directive', directiveId),
  getWatchlist: () => ipcRenderer.invoke('get-watchlist'),
  getVitals: () => ipcRenderer.invoke('get-vitals'),
  getSessions: () => ipcRenderer.invoke('get-sessions'),
  switchSession: (sessionId) => ipcRenderer.invoke('switch-session', sessionId),
  newSession: () => ipcRenderer.invoke('new-session'),
  renameSession: (sessionId, title) => ipcRenderer.invoke('rename-session', { session_id: sessionId, title }),
  deleteSession: (sessionId) => ipcRenderer.invoke('delete-session', sessionId),
  checkEmail: () => ipcRenderer.invoke('check-email'),
  listSentEmails: () => ipcRenderer.invoke('send-slash-command', '/email sent'),
  deleteSentEmail: (index = 1) => ipcRenderer.invoke('send-slash-command', `/email delete ${index}`),

  getCalendarEvents: () => ipcRenderer.invoke('get-calendar-events'),

  toggleFullScreen: () => ipcRenderer.invoke('toggle-fullscreen'),
  minimize: () => ipcRenderer.invoke('window-minimize'),
  close: () => ipcRenderer.invoke('window-close')
})
