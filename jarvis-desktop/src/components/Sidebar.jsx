import React, { useState, useEffect } from 'react'
import './Sidebar.css'

export default function Sidebar({ isOpen, onClose, currentSessionId, sessions: sessionsProp = [], deletingSessionIds = new Set(), sessionToast = null, onSwitchSession, onNewSession, onDeleteSession }) {
  const [projects, setProjects] = useState([])
  const [reminders, setReminders] = useState([])
  const [watchlist, setWatchlist] = useState([])
  const [fallbackSessions, setFallbackSessions] = useState([])

  const sessions = sessionsProp && sessionsProp.length > 0 ? sessionsProp : fallbackSessions

  const fetchLiveData = async () => {
    if (window.jarvis?.getProjects) {
      try {
        const p = await window.jarvis.getProjects()
        setProjects(Array.isArray(p) ? p : [])
      } catch (e) {
        console.log('Error fetching projects:', e)
      }
    }
    if (window.jarvis?.getReminders) {
      try {
        const r = await window.jarvis.getReminders()
        setReminders(Array.isArray(r) ? r : [])
      } catch (e) {
        console.log('Error fetching reminders:', e)
      }
    }
    if (window.jarvis?.getWatchlist) {
      try {
        const w = await window.jarvis.getWatchlist()
        setWatchlist(Array.isArray(w) ? w : [])
      } catch (e) {
        console.log('Error fetching watchlist:', e)
      }
    }
    // One-time fallback for sessions if WS payload has not arrived yet
    if ((!sessionsProp || sessionsProp.length === 0) && window.jarvis?.getSessions) {
      try {
        const s = await window.jarvis.getSessions()
        if (Array.isArray(s)) setFallbackSessions(s)
      } catch (e) {
        console.log('Error initial getSessions fallback:', e)
      }
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchLiveData()
    }
  }, [isOpen, currentSessionId])

  const handleDeleteSession = (e, sid) => {
    e.stopPropagation()
    if (e.preventDefault) e.preventDefault()
    
    console.log('[SESSION DELETE] Clicked target session ID:', sid)
    
    if (onDeleteSession) {
      onDeleteSession(sid)
    } else if (window.jarvis?.deleteSession) {
      window.jarvis.deleteSession(sid)
    }
    // Pessimistic deletion: do NOT alter local sessions state manually here.
    // App.jsx will update deletingSessionIds and clear the item upon WS confirmation.
  }

  const handleCreateProject = () => {
    const name = window.prompt('Enter new project name:')
    if (name && name.trim()) {
      if (window.jarvis?.createProject) {
        window.jarvis.createProject(name.trim())
      }
      setProjects(prev => [{ project_id: `proj_${Date.now()}`, name: name.trim(), status: 'Active' }, ...prev])
    }
  }

  const handleDeleteProject = (e, projectId) => {
    e.stopPropagation()
    if (e.preventDefault) e.preventDefault()
    if (window.jarvis?.deleteProject) {
      window.jarvis.deleteProject(projectId)
    }
    setProjects(prev => prev.filter(p => (p.project_id || p.id) !== projectId))
  }

  const formatTimestamp = (ts) => {
    if (!ts) return 'Recent'
    try {
      const d = new Date(typeof ts === 'number' && ts < 1e11 ? ts * 1000 : ts)
      return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
    } catch (e) {
      return 'Recent'
    }
  }

  if (!isOpen) return null

  return (
    <div className="sidebar-container">
      <div className="sidebar-header">
        <div className="sidebar-title">SAVED SESSIONS & TELEMETRY</div>
        <button className="sidebar-close-btn" onClick={onClose}>✕</button>
      </div>

      {sessionToast && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.2)',
          border: '1px solid #ef4444',
          color: '#f87171',
          padding: '8px 12px',
          margin: '8px 16px 0 16px',
          borderRadius: '4px',
          fontSize: '0.8rem'
        }}>
          {sessionToast}
        </div>
      )}

      {/* SESSIONS SECTION */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">
          <span>Past Sessions</span>
          <button className="sidebar-action-btn" onClick={() => onNewSession && onNewSession()}>+ New Chat</button>
        </div>
        <div className="sidebar-list">
          {sessions.length === 0 ? (
            <div className="sidebar-empty">No past sessions</div>
          ) : (
            sessions.map((s, i) => {
              const sid = s.session_id || i
              const isDeleting = deletingSessionIds && deletingSessionIds.has(s.session_id)
              return (
                <div 
                  key={sid} 
                  className={`sidebar-item ${s.session_id === currentSessionId ? 'active' : ''} ${isDeleting ? 'deleting' : ''}`}
                  onClick={() => !isDeleting && onSwitchSession && onSwitchSession(s.session_id)}
                  style={{
                    cursor: isDeleting ? 'not-allowed' : 'pointer',
                    opacity: isDeleting ? 0.5 : 1,
                    pointerEvents: isDeleting ? 'none' : 'auto'
                  }}
                >
                  <div className="sidebar-item-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div className="sidebar-item-name">{s.title || 'Untitled Session'}</div>
                    <button 
                      className="sidebar-delete-btn"
                      title={isDeleting ? 'Deleting session...' : 'Delete session'}
                      disabled={isDeleting}
                      onClick={(e) => handleDeleteSession(e, s.session_id)}
                    >
                      {isDeleting ? '⏳' : '🗑️'}
                    </button>
                  </div>
                  <div className="sidebar-item-sub">
                    {isDeleting ? 'Deleting session...' : `${formatTimestamp(s.last_active)} · ${s.message_count || 0} msgs`}
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* PROJECTS SECTION */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">
          <span>Projects</span>
          <button className="sidebar-action-btn" onClick={handleCreateProject}>+ New Project</button>
        </div>
        <div className="sidebar-list">
          {projects.length === 0 ? (
            <div className="sidebar-empty">No active projects</div>
          ) : (
            projects.map((p, i) => {
              const pid = p.project_id || p.id || `proj_${i}`
              return (
                <div key={pid} className="sidebar-item">
                  <div className="sidebar-item-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div className="sidebar-item-name">{p.name || p.title || 'Untitled Project'}</div>
                    <button 
                      className="sidebar-delete-btn"
                      title="Delete project"
                      onClick={(e) => handleDeleteProject(e, pid)}
                    >
                      🗑️
                    </button>
                  </div>
                  <div className="sidebar-item-sub">
                    {p.path ? `${p.path} · ` : ''}{p.status || 'Active'}
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* REMINDERS SECTION */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">
          <span>Calendar & Reminders</span>
          <span>{reminders.length}</span>
        </div>
        <div className="sidebar-list">
          {reminders.length === 0 ? (
            <div className="sidebar-empty">No Google Calendar events</div>
          ) : (
            reminders.map((r, i) => (
              <div key={i} className="sidebar-item">
                <div className="sidebar-item-name">{r.summary || r.title || r.text || 'Calendar Event'}</div>
                <div className="sidebar-item-sub">
                  📅 {r.start ? new Date(r.start).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : (r.due_date || 'Upcoming')}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* WATCHLIST SECTION */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">
          <span>Market Watchlist</span>
          <span>{watchlist.length}</span>
        </div>
        <div className="sidebar-list">
          {watchlist.length === 0 ? (
            <div className="sidebar-empty">No tickers watched</div>
          ) : (
            watchlist.map((w, i) => (
              <div key={i} className="sidebar-item">
                <div className="sidebar-item-name">{w.ticker || w.symbol}</div>
                <div className="sidebar-item-sub">
                  {w.condition ? `${w.condition.toUpperCase()} $${w.target_price}` : 'Tracked'}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
