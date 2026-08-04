import React from 'react'
import './TitleBar.css'

export default function TitleBar({ onToggleSidebar, isSidebarOpen, isConnected = true }) {
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
    <div className="title-bar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div className="title-bar-label">J.A.R.V.I.S.</div>
        <div style={{
          fontSize: '9px',
          padding: '2px 6px',
          borderRadius: '4px',
          letterSpacing: '1px',
          background: isConnected ? 'rgba(0, 217, 255, 0.1)' : 'rgba(255, 68, 68, 0.15)',
          border: isConnected ? '0.5px solid #0d3a3a' : '0.5px solid #ff4444',
          color: isConnected ? '#00D9FF' : '#ff6666'
        }}>
          {isConnected ? 'ONLINE' : 'RECONNECTING...'}
        </div>
        <button
          onClick={onToggleSidebar}
          style={{
            background: isSidebarOpen ? 'rgba(0,217,255,0.15)' : 'transparent',
            border: '0.5px solid #0d3a3a',
            color: isSidebarOpen ? '#00D9FF' : '#555',
            fontSize: '9px',
            padding: '2px 6px',
            borderRadius: '4px',
            cursor: 'pointer',
            WebkitAppRegion: 'no-drag',
            letterSpacing: '1px'
          }}
          title="Toggle Sidebar (Tab / S)"
        >
          TELEMETRY {isSidebarOpen ? '◄' : '►'}
        </button>
      </div>

      <div className="title-bar-controls">
        <button
          className="title-btn minimize"
          onClick={handleMinimize}
          title="Minimize"
        />
        <button
          className="title-btn close"
          onClick={handleClose}
          title="Close"
        />
      </div>
    </div>
  )
}
