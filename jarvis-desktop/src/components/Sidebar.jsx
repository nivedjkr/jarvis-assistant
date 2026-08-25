import React, { useState, useEffect } from 'react'
import './Sidebar.css'
import MiniCalendar from './MiniCalendar'

export default function Sidebar({ isOpen, onClose, currentSessionId, onSwitchSession, onNewSession, onDeleteSession, onOpenFullCalendar }) {
  const [projects, setProjects] = useState([])
  const [reminders, setReminders] = useState([])
  const [watchlist, setWatchlist] = useState([])
  const [sessions, setSessions] = useState([])

  const fetchLiveData = async () => {
    if (window.jarvis?.getSessions) {
      try {
        const s = await window.jarvis.getSessions()
        setSessions(Array.isArray(s) ? s : [])
      } catch (e) {
        console.log('Error fetching sessions:', e)
      }
    }
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
  }

  useEffect(() => {
    if (isOpen) {
      fetchLiveData()
      const interval = setInterval(fetchLiveData, 15000)
      return () => clearInterval(interval)
    }
  }, [isOpen])

  const handleDeleteSession = (e, sid) => {
    e.stopPropagation()
    if (window.confirm('Delete this conversation permanently?')) {
      if (onDeleteSession) {
        onDeleteSession(sid)
      } else if (window.jarvis?.deleteSession) {
        window.jarvis.deleteSession(sid)
      }
      setSessions(prev => prev.filter(s => s.session_id !== sid))
      if (sid === currentSessionId) {
        if (onNewSession) onNewSession()
        else if (window.jarvis?.newSession) window.jarvis.newSession()
      }
    }
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
            sessions.map((s, i) => (
              <div 
                key={s.session_id || i} 
                className={`sidebar-item ${s.session_id === currentSessionId ? 'active' : ''}`}
                onClick={() => onSwitchSession && onSwitchSession(s.session_id)}
                style={{ cursor: 'pointer' }}
              >
                <div className="sidebar-item-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div className="sidebar-item-name">{s.title || 'Untitled Session'}</div>
                  <button 
                    className="sidebar-delete-btn"
                    title="Delete session"
                    onClick={(e) => handleDeleteSession(e, s.session_id)}
                  >
                    🗑️
                  </button>
                </div>
                <div className="sidebar-item-sub">
                  {formatTimestamp(s.last_active)} · {s.message_count || 0} msgs
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* MINI CALENDAR SECTION */}
      <MiniCalendar onOpenFullCalendar={onOpenFullCalendar} />

      {/* PROJECTS SECTION */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">
          <span>Projects</span>
          <span>{projects.length}</span>
        </div>
        <div className="sidebar-list">
          {projects.length === 0 ? (
            <div className="sidebar-empty">No active projects</div>
          ) : (
            projects.map((p, i) => (
              <div key={i} className="sidebar-item">
                <div className="sidebar-item-name">{p.name || p.title || 'Project'}</div>
                <div className="sidebar-item-sub">
                  {p.category ? `${p.category.toUpperCase()} · ` : ''}{p.status || 'Active'}
                </div>
              </div>
            ))
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
