import React, { useState, useEffect } from 'react'
import './TitleBar.css'

export default function TitleBar({ isConnected = true }) {
  const [timeStr, setTimeStr] = useState('')

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

  const handleHelp = () => {
    if (window.jarvis?.sendSlashCommand) {
      window.jarvis.sendSlashCommand('/help')
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
        <div className={`status-dot ${isConnected ? 'online' : 'offline'}`} />
        <span className="brand-mark">J.A.R.V.I.S. // COMMAND DECK</span>
      </div>

      <div className="title-right">
        <span className="session-id">SESSION: #JVS-887B</span>
        <span className="live-clock">{timeStr || '00:00:00'}</span>
        <div className="title-controls">
          <button className="control-btn help" onClick={handleHelp} title="Show System Help">?</button>
          <button className="control-btn" onClick={handleMinimize} title="Minimize">—</button>
          <button className="control-btn close" onClick={handleClose} title="Close">✕</button>
        </div>
      </div>
    </div>
  )
}
