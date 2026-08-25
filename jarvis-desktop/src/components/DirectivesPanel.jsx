import React, { useState, useEffect } from 'react'
import './DirectivesPanel.css'

export default function DirectivesPanel({ isConnected = true, lastStateUpdate = null, isOpen = true, onClose }) {
  const [directives, setDirectives] = useState([
    { id: 1, text: 'Review portfolio AAPL target', completed: false },
    { id: 2, text: 'Backup SQLite memory DB', completed: false },
    { id: 3, text: 'Check internship board updates', completed: false }
  ])
  const [flashingItem, setFlashingItem] = useState(null)

  const fetchDirectives = async () => {
    if (window.jarvis?.getReminders) {
      try {
        const reminders = await window.jarvis.getReminders()
        if (Array.isArray(reminders) && reminders.length > 0) {
          const formatted = reminders.map((r, i) => ({
            id: r.id || i,
            text: r.message || r.text || r.task || 'Pending directive',
            completed: Boolean(r.completed)
          }))
          setDirectives(formatted)
        }
      } catch (e) {
        // Keep existing directives on error
      }
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchDirectives()
      const timer = setInterval(fetchDirectives, 5000)
      return () => clearInterval(timer)
    }
  }, [isConnected, isOpen])

  // Handle incoming real-time state_update events over WebSocket
  useEffect(() => {
    if (!lastStateUpdate || !isOpen) return
    const { domain, payload } = lastStateUpdate
    if (domain === 'directives' || domain === 'inventory') {
      fetchDirectives()
      if (payload && payload.text) {
        setDirectives(prev => {
          const exists = prev.some(d => d.text === payload.text)
          if (!exists) {
            return [{ id: Date.now(), text: payload.text, completed: false }, ...prev]
          }
          return prev
        })
        setFlashingItem(payload.text)
      } else {
        setFlashingItem('panel')
      }
      const t = setTimeout(() => setFlashingItem(null), 1600)
      return () => clearTimeout(t)
    }
  }, [lastStateUpdate, isOpen])

  const toggleDirective = (id) => {
    setDirectives(prev =>
      prev.map(item =>
        item.id === id ? { ...item, completed: !item.completed } : item
      )
    )
  }

  if (!isOpen) return null

  return (
    <aside className={`directives-panel ${flashingItem === 'panel' ? 'state-flash-highlight' : ''}`}>
      <div className="directives-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>DIRECTIVES</span>
        {onClose && (
          <button 
            className="directives-close-btn" 
            onClick={onClose} 
            title="Close Directives Panel"
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '12px',
              padding: '0 4px',
              lineHeight: 1
            }}
          >
            ✕
          </button>
        )}
      </div>
      
      <div className="directives-list">
        {directives.length === 0 ? (
          <div className="no-directives">NO ACTIVE DIRECTIVES</div>
        ) : (
          directives.map(item => (
            <div
              key={item.id}
              className={`directive-item ${item.completed ? 'completed' : ''} ${flashingItem === item.text ? 'state-flash-highlight' : ''}`}
              onClick={() => toggleDirective(item.id)}
            >
              <span className="directive-marker">
                {item.completed ? '◇' : '◆'}
              </span>
              <span className="directive-text">{item.text}</span>
            </div>
          ))
        )}
      </div>
    </aside>
  )
}
