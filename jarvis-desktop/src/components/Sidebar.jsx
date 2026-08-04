import React, { useState, useEffect } from 'react'
import './Sidebar.css'

export default function Sidebar({ isOpen, onClose }) {
  const [projects, setProjects] = useState([])
  const [reminders, setReminders] = useState([])
  const [watchlist, setWatchlist] = useState([])

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
  }

  useEffect(() => {
    if (isOpen) {
      fetchLiveData()
      const interval = setInterval(fetchLiveData, 60000)
      return () => clearInterval(interval)
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div className="sidebar-container">
      <div className="sidebar-header">
        <div className="sidebar-title">LIVE TELEMETRY</div>
        <button className="sidebar-close-btn" onClick={onClose}>✕</button>
      </div>

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
          <span>Reminders</span>
          <span>{reminders.length}</span>
        </div>
        <div className="sidebar-list">
          {reminders.length === 0 ? (
            <div className="sidebar-empty">No pending reminders</div>
          ) : (
            reminders.map((r, i) => (
              <div key={i} className="sidebar-item">
                <div className="sidebar-item-name">{r.text}</div>
                <div className="sidebar-item-sub">
                  {r.due_date ? `Due: ${r.due_date.slice(11, 16)}` : 'Pending'}
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
