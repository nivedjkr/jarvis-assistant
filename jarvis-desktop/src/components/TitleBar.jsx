import React, { useState, useEffect } from 'react'
import './TitleBar.css'

export default function TitleBar({ 
  isConnected = true, 
  onToggleSessions, 
  onToggleCalendar, 
  isCalendarOpen = false,
  onToggleDirectives,
  isDirectivesOpen = true
}) {
  const [timeStr, setTimeStr] = useState('')
  const [isFullscreen, setIsFullscreen] = useState(false)

  useEffect(() => {
    const updateTime = () => {
      const now = new Date()
      const hours = String(now.getHours()).padStart(2, '0')
      const minutes = String(now.getMinutes()).padStart(2, '0')
      const seconds = String(now.getSeconds()).padStart(2, '0')
      setTimeStr(`${hours}:${minutes}:${seconds}`)
    }
    updateTime()
    const timer = setInterval(updateTime, 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'F11') {
        e.preventDefault()
        handleToggleFullScreen()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const handleHelp = () => {
    if (window.jarvis?.sendSlashCommand) {
      window.jarvis.sendSlashCommand('/help')
    }
  }

  const handleToggleFullScreen = async () => {
    if (window.jarvis?.toggleFullScreen) {
      const fsState = await window.jarvis.toggleFullScreen()
      setIsFullscreen(Boolean(fsState))
    }
  }

  const handleMinimize = () => {
    if (window.jarvis?.minimize) {
      window.jarvis.minimize()
    }
  }

  const handleClose = () => {
    if (window.jarvis?.close) {
      window.jarvis.close()
    }
  }

  return (
    <div className="command-title-bar">
      <div className="title-left">
        <button 
          className="sessions-toggle-btn" 
          onClick={onToggleSessions} 
          title="Past Sessions (Conversations)"
        >
          ⋮
        </button>
        <button 
          className={`sessions-toggle-btn ${isCalendarOpen ? 'active' : ''}`}
          onClick={onToggleCalendar} 
          title="Google Calendar & Schedule"
          style={{ marginLeft: '4px' }}
        >
          📅
        </button>
        <button 
          className={`sessions-toggle-btn ${isDirectivesOpen ? 'active' : ''}`}
          onClick={onToggleDirectives} 
          title="Directives & Tasks"
          style={{ marginLeft: '4px' }}
        >
          📋
        </button>
        <div className={`status-dot ${isConnected ? 'online' : 'offline'}`} />
        <span className="brand-mark">J.A.R.V.I.S. // COMMAND DECK</span>
      </div>

      <div className="title-right">
        <span className="session-id">SESSION: #JVS-887B</span>
        <span className="live-clock">{timeStr || '00:00:00'}</span>
        <div className="title-controls">
          <button className="control-btn help" onClick={handleHelp} title="Show System Help">?</button>
          <button className="control-btn" onClick={handleToggleFullScreen} title="Toggle Fullscreen (F11)">
            {isFullscreen ? '❐' : '⛶'}
          </button>
          <button className="control-btn" onClick={handleMinimize} title="Minimize">—</button>
          <button className="control-btn close" onClick={handleClose} title="Close">✕</button>
        </div>
      </div>
    </div>
  )
}
