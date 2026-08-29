import React, { useState, useEffect } from 'react'
import './DirectivesPanel.css'

export default function DirectivesPanel({ isConnected = true, lastStateUpdate = null, isOpen = true, onClose }) {
  const [directives, setDirectives] = useState([])
  const [flashingItem, setFlashingItem] = useState(null)

  const fetchDirectives = async () => {
    const fn = window.jarvis?.getDirectives || window.jarvis?.getReminders
    if (fn) {
      try {
        const raw = await fn()
        if (Array.isArray(raw)) {
          const formatted = raw.map((r, i) => {
            const displayTitle = r.title || r.text || r.summary || (r.id ? `Directive #${r.id}` : `Directive ${i + 1}`)
            return {
              id: r.id || i,
              text: displayTitle,
              title: displayTitle,
              completed: Boolean(r.completed || r.status === 'completed'),
              status: r.status || (r.completed ? 'completed' : 'active')
            }
          })
          setDirectives(formatted)
        }
      } catch (e) {
        console.log('[DIRECTIVES] Error fetching directives:', e)
      }
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchDirectives()
      const timer = setInterval(fetchDirectives, 10000)
      return () => clearInterval(timer)
    }
  }, [isConnected, isOpen])

  // Handle incoming real-time state_update events over WebSocket
  useEffect(() => {
    if (!lastStateUpdate || !isOpen) return
    const { domain, payload, type } = lastStateUpdate
    if (domain === 'directives' || domain === 'inventory' || type === 'directive_completed' || type === 'directive_deleted') {
      fetchDirectives()
      if (payload && payload.text) {
        setFlashingItem(payload.text)
        const t = setTimeout(() => setFlashingItem(null), 1600)
        return () => clearTimeout(t)
      }
    }
  }, [lastStateUpdate, isOpen])

  const toggleDirective = (id) => {
    if (window.jarvis?.completeDirective) {
      window.jarvis.completeDirective(id)
    }
    setDirectives(prev =>
      prev.map(item =>
        item.id === id ? { ...item, completed: !item.completed, status: !item.completed ? 'completed' : 'active' } : item
      )
    )
  }

  const handleDeleteDirective = (e, id) => {
    e.stopPropagation()
    if (e.preventDefault) e.preventDefault()
    if (window.jarvis?.deleteDirective) {
      window.jarvis.deleteDirective(id)
    }
    setDirectives(prev => prev.filter(d => d.id !== id))
  }

  if (!isOpen) return null

  const activeDirectives = directives.filter(d => !d.completed)
  const completedDirectives = directives.filter(d => d.completed)

  return (
    <aside className={`directives-panel ${flashingItem === 'panel' ? 'state-flash-highlight' : ''}`}>
      <div className="directives-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>DIRECTIVES & GOALS</span>
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
          <>
            {activeDirectives.length > 0 && (
              <div className="directives-group-title" style={{ fontSize: '10px', color: 'var(--text-muted)', margin: '4px 0 2px 0', letterSpacing: '0.5px' }}>ACTIVE ({activeDirectives.length})</div>
            )}
            {activeDirectives.map(item => (
              <div
                key={item.id}
                className={`directive-item ${flashingItem === item.text ? 'state-flash-highlight' : ''}`}
                onClick={() => toggleDirective(item.id)}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
                  <span className="directive-marker">◆</span>
                  <span className="directive-text">{item.text}</span>
                </div>
                <button
                  className="sidebar-delete-btn"
                  title="Delete directive"
                  onClick={(e) => handleDeleteDirective(e, item.id)}
                  style={{ background: 'transparent', border: 'none', cursor: 'pointer', opacity: 0.6, fontSize: '11px' }}
                >
                  ✕
                </button>
              </div>
            ))}

            {completedDirectives.length > 0 && (
              <div className="directives-group-title" style={{ fontSize: '10px', color: 'var(--text-muted)', margin: '8px 0 2px 0', letterSpacing: '0.5px' }}>COMPLETED ({completedDirectives.length})</div>
            )}
            {completedDirectives.map(item => (
              <div
                key={item.id}
                className="directive-item completed"
                onClick={() => toggleDirective(item.id)}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', opacity: 0.5 }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
                  <span className="directive-marker">◇</span>
                  <span className="directive-text" style={{ textDecoration: 'line-through' }}>{item.text}</span>
                </div>
                <button
                  className="sidebar-delete-btn"
                  title="Delete directive"
                  onClick={(e) => handleDeleteDirective(e, item.id)}
                  style={{ background: 'transparent', border: 'none', cursor: 'pointer', opacity: 0.6, fontSize: '11px' }}
                >
                  ✕
                </button>
              </div>
            ))}
          </>
        )}
      </div>
    </aside>
  )
}
