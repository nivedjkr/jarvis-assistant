import React, { useState, useEffect } from 'react'
import './DirectivesPanel.css'

export default function DirectivesPanel({ isConnected = true, lastStateUpdate = null, isOpen = true, onClose }) {
  const [directives, setDirectives] = useState([])
  const [flashingItem, setFlashingItem] = useState(null)
  const [deletingIds, setDeletingIds] = useState(new Set())
  const [errorToast, setErrorToast] = useState(null)

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
          setDeletingIds(new Set())
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
    if (deletingIds.has(id)) return
    if (window.jarvis?.completeDirective) {
      window.jarvis.completeDirective(id)
    }
    setDirectives(prev =>
      prev.map(item =>
        item.id === id ? { ...item, completed: !item.completed, status: !item.completed ? 'completed' : 'active' } : item
      )
    )
  }

  const handleDeleteDirective = async (e, id) => {
    e.stopPropagation()
    if (e.preventDefault) e.preventDefault()
    setDeletingIds(prev => new Set(prev).add(id))
    if (window.jarvis?.deleteDirective) {
      const res = await window.jarvis.deleteDirective(id)
      if (res && res.status === 'offline') {
        setDeletingIds(prev => {
          const next = new Set(prev)
          next.delete(id)
          return next
        })
        setErrorToast('Backend disconnected — could not delete directive')
        setTimeout(() => setErrorToast(null), 4000)
      }
    }
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

      {errorToast && (
        <div className="directives-error-toast" style={{ background: '#721c24', color: '#f8d7da', padding: '6px 10px', fontSize: '11px', borderRadius: '4px', margin: '4px 8px' }}>
          ⚠️ {errorToast}
        </div>
      )}
      
      <div className="directives-list">
        {directives.length === 0 ? (
          <div className="no-directives">NO ACTIVE DIRECTIVES</div>
        ) : (
          <>
            {activeDirectives.length > 0 && (
              <div className="directives-group-title" style={{ fontSize: '10px', color: 'var(--text-muted)', margin: '4px 0 2px 0', letterSpacing: '0.5px' }}>ACTIVE ({activeDirectives.length})</div>
            )}
            {activeDirectives.map(item => {
              const isDeleting = deletingIds.has(item.id)
              return (
                <div
                  key={item.id}
                  className={`directive-item ${flashingItem === item.text ? 'state-flash-highlight' : ''}`}
                  onClick={() => toggleDirective(item.id)}
                  style={{
                    display: 'flex',
                    justify: 'space-between',
                    alignItems: 'center',
                    opacity: isDeleting ? 0.4 : 1,
                    pointerEvents: isDeleting ? 'none' : 'auto'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
                    <span className="directive-marker">◆</span>
                    <span className="directive-text">{item.text}</span>
                  </div>
                  <button
                    className="sidebar-delete-btn"
                    title="Delete directive"
                    onClick={(e) => handleDeleteDirective(e, item.id)}
                    disabled={isDeleting}
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', opacity: 0.6, fontSize: '11px' }}
                  >
                    {isDeleting ? '⏳' : '✕'}
                  </button>
                </div>
              )
            })}

            {completedDirectives.length > 0 && (
              <div className="directives-group-title" style={{ fontSize: '10px', color: 'var(--text-muted)', margin: '8px 0 2px 0', letterSpacing: '0.5px' }}>COMPLETED ({completedDirectives.length})</div>
            )}
            {completedDirectives.map(item => {
              const isDeleting = deletingIds.has(item.id)
              return (
                <div
                  key={item.id}
                  className="directive-item completed"
                  onClick={() => toggleDirective(item.id)}
                  style={{
                    display: 'flex',
                    justify: 'space-between',
                    alignItems: 'center',
                    opacity: isDeleting ? 0.3 : 0.5,
                    pointerEvents: isDeleting ? 'none' : 'auto'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
                    <span className="directive-marker">◇</span>
                    <span className="directive-text" style={{ textDecoration: 'line-through' }}>{item.text}</span>
                  </div>
                  <button
                    className="sidebar-delete-btn"
                    title="Delete directive"
                    onClick={(e) => handleDeleteDirective(e, item.id)}
                    disabled={isDeleting}
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', opacity: 0.6, fontSize: '11px' }}
                  >
                    {isDeleting ? '⏳' : '✕'}
                  </button>
                </div>
              )
            })}
          </>
        )}
      </div>
    </aside>
  )
}
