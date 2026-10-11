import React, { useState, useEffect } from 'react'
import './StarkDeckPanel.css'

export default function StarkDeckPanel({
  isConnected = true,
  lastStateUpdate = null,
  isOpen = true,
  onClose,
  activeDeck: controlledDeck,
  onDeckChange
}) {
  const [localDeck, setLocalDeck] = useState('directives')
  const activeDeck = controlledDeck !== undefined ? controlledDeck : localDeck
  const setActiveDeck = (deck) => {
    setLocalDeck(deck)
    if (onDeckChange) onDeckChange(deck)
  }
  const [filter, setFilter] = useState('all') // 'all' | 'directives' | 'calendar' | 'completed'

  // Directives State
  const [directives, setDirectives] = useState([])
  const [newDirectiveText, setNewDirectiveText] = useState('')
  const [isAddingDirective, setIsAddingDirective] = useState(false)
  const [isSyncing, setIsSyncing] = useState(false)
  const [deletingIds, setDeletingIds] = useState(new Set())

  // Dispatches (Email) State
  const [emailTab, setEmailTab] = useState('inbox')
  const [emails, setEmails] = useState([])
  const [sentEmails, setSentEmails] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)

  // Missions State
  const [missions, setMissions] = useState([])

  // Fetch Directives & Sync with Google Calendar
  const fetchDirectives = async () => {
    setIsSyncing(true)
    const fn = window.jarvis?.getDirectives || window.jarvis?.getReminders
    try {
      if (fn) {
        const raw = await fn()
        if (Array.isArray(raw)) {
          setDirectives(raw)
        }
      } else {
        const res = await fetch('http://127.0.0.1:8765/directives')
        if (res.ok) {
          const raw = await res.json()
          if (Array.isArray(raw)) setDirectives(raw)
        }
      }
    } catch (e) {
      console.warn('[DECK] Error fetching directives:', e)
    } finally {
      setTimeout(() => setIsSyncing(false), 400)
    }
  }

  // Fetch Dispatches (Emails)
  const fetchEmails = async () => {
    if (window.jarvis?.checkEmail && emailTab === 'inbox') {
      window.jarvis.checkEmail()
    }
    if (window.jarvis?.getSentEmails && emailTab === 'sent') {
      try {
        const res = await window.jarvis.getSentEmails()
        if (res && Array.isArray(res.sent_emails)) {
          setSentEmails(res.sent_emails)
        }
      } catch (err) {
        console.warn('[DECK] Error fetching sent emails:', err)
      }
    }
  }

  // Fetch Missions
  const fetchMissions = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8765/missions')
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data)) setMissions(data)
      }
    } catch (e) {
      // Missions manager offline fallback
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchDirectives()
      if (activeDeck === 'dispatches') fetchEmails()
      if (activeDeck === 'missions') fetchMissions()
    }
  }, [isOpen, activeDeck, emailTab, isConnected])

  // Handle incoming real-time state updates
  useEffect(() => {
    if (!lastStateUpdate || !isOpen) return
    const { domain, payload, type } = lastStateUpdate
    if (domain === 'directives' || type === 'directive_completed' || type === 'directive_deleted') {
      fetchDirectives()
    }
    if (domain === 'email' || domain === 'sent_email') {
      if (payload && Array.isArray(payload.emails)) {
        setEmails(payload.emails)
        setUnreadCount(payload.unread_count ?? payload.emails.length)
      }
      if (payload && Array.isArray(payload.sent_emails)) {
        setSentEmails(payload.sent_emails)
      }
    }
    if (domain === 'missions') {
      fetchMissions()
    }
  }, [lastStateUpdate, isOpen])

  // Add Directive
  const handleAddDirective = async (e) => {
    if (e.key === 'Enter' && newDirectiveText.trim() && !isAddingDirective) {
      setIsAddingDirective(true)
      const textToAdd = newDirectiveText.trim()
      setNewDirectiveText('')

      try {
        if (window.jarvis?.createDirective) {
          await window.jarvis.createDirective(textToAdd)
        } else {
          await fetch('http://127.0.0.1:8765/directives', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: textToAdd })
          })
        }
        await fetchDirectives()
      } catch (err) {
        console.warn('Error creating directive:', err)
      } finally {
        setIsAddingDirective(false)
      }
    }
  }

  // Toggle Complete
  const handleToggleComplete = async (id, currentCompleted) => {
    if (String(id).startsWith('cal_')) return // Calendar events are read-only
    if (window.jarvis?.completeDirective) {
      await window.jarvis.completeDirective(id)
    } else {
      await fetch(`http://127.0.0.1:8765/directives/${id}/complete`, { method: 'POST' })
    }
    setDirectives(prev =>
      prev.map(d => (d.id === id ? { ...d, completed: !currentCompleted } : d))
    )
  }

  // Delete Directive
  const handleDeleteDirective = async (e, id) => {
    e.stopPropagation()
    if (String(id).startsWith('cal_')) return
    setDeletingIds(prev => new Set(prev).add(id))

    try {
      if (window.jarvis?.deleteDirective) {
        await window.jarvis.deleteDirective(id)
      } else {
        await fetch(`http://127.0.0.1:8765/directives/${id}`, { method: 'DELETE' })
      }
      setDirectives(prev => prev.filter(d => d.id !== id))
    } catch (err) {
      console.warn('Error deleting directive:', err)
    } finally {
      setDeletingIds(prev => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  if (!isOpen) return null

  // Filter directives
  const filteredDirectives = directives.filter(d => {
    if (filter === 'completed') return d.completed
    if (filter === 'calendar') return d.source === 'calendar'
    if (filter === 'directives') return d.source !== 'calendar' && !d.completed
    // 'all' shows uncompleted directives + calendar events
    return !d.completed
  })

  return (
    <aside className="stark-deck-panel">
      {/* Top Deck Navigation Tabs */}
      <div className="deck-nav-bar">
        <div className="deck-tabs-group">
          <button
            className={`deck-tab-btn ${activeDeck === 'directives' ? 'active' : ''}`}
            onClick={() => setActiveDeck('directives')}
            title="Directives, Google Calendar & Reminders"
          >
            DIRECTIVES
          </button>
          <button
            className={`deck-tab-btn ${activeDeck === 'dispatches' ? 'active' : ''}`}
            onClick={() => setActiveDeck('dispatches')}
            title="Dispatches & Gmail Inbox"
          >
            DISPATCHES
            {unreadCount > 0 && <span className="deck-unread-dot"></span>}
          </button>
          <button
            className={`deck-tab-btn ${activeDeck === 'missions' ? 'active' : ''}`}
            onClick={() => setActiveDeck('missions')}
            title="Autonomous Multi-Step Missions"
          >
            MISSIONS
          </button>
        </div>

        {onClose && (
          <button className="deck-close-btn" onClick={onClose} title="Collapse Command Deck">
            ✕
          </button>
        )}
      </div>

      {/* ================= DECK 1: DIRECTIVES & CALENDAR ================= */}
      {activeDeck === 'directives' && (
        <div className="deck-content-pane">
          {/* Deck Header & Sync Controls */}
          <div className="deck-header-controls">
            <div className="deck-filter-pills">
              <button
                className={`filter-pill ${filter === 'all' ? 'active' : ''}`}
                onClick={() => setFilter('all')}
              >
                ALL
              </button>
              <button
                className={`filter-pill ${filter === 'directives' ? 'active' : ''}`}
                onClick={() => setFilter('directives')}
              >
                TASKS
              </button>
              <button
                className={`filter-pill ${filter === 'calendar' ? 'active' : ''}`}
                onClick={() => setFilter('calendar')}
              >
                CALENDAR
              </button>
              <button
                className={`filter-pill ${filter === 'completed' ? 'active' : ''}`}
                onClick={() => setFilter('completed')}
              >
                DONE
              </button>
            </div>

            <button
              className={`deck-sync-btn ${isSyncing ? 'spinning' : ''}`}
              onClick={fetchDirectives}
              title="Sync with Google Calendar & DB"
            >
              ⟳
            </button>
          </div>

          {/* Sync Status Banner */}
          <div className="deck-sync-banner">
            <span className="sync-status-icon">//</span>
            <span className="sync-status-text">SYNCED // GOOGLE CALENDAR & PERSISTENT DB</span>
          </div>

          {/* Directives List */}
          <div className="deck-items-list">
            {filteredDirectives.length === 0 ? (
              <div className="deck-empty-state">
                <span className="empty-symbol">[--]</span>
                <span className="empty-text">NO DIRECTIVES IN THIS VIEW</span>
                <span className="empty-sub">Type a directive below to schedule</span>
              </div>
            ) : (
              filteredDirectives.map(item => {
                const isCalendar = item.source === 'calendar'
                const isMission = item.source === 'mission'
                const isDeleting = deletingIds.has(item.id)

                let badgeLabel = 'DIRECTIVE'
                let badgeClass = 'badge-dir'
                if (isCalendar) {
                  badgeLabel = item.time ? `CAL // ${item.time}` : 'CALENDAR'
                  badgeClass = 'badge-cal'
                } else if (isMission) {
                  badgeLabel = 'MISSION'
                  badgeClass = 'badge-mis'
                }

                return (
                  <div
                    key={item.id}
                    className={`deck-item ${item.completed ? 'completed' : ''} ${isCalendar ? 'cal-item' : ''}`}
                    onClick={() => handleToggleComplete(item.id, item.completed)}
                    style={{ opacity: isDeleting ? 0.3 : 1 }}
                  >
                    <div className="deck-item-left">
                      <span className={`deck-marker ${item.completed ? 'done' : isCalendar ? 'cal' : 'active'}`}>
                        {item.completed ? '[X]' : isCalendar ? '[C]' : '[-]'}
                      </span>
                      <div className="deck-item-info">
                        <span className="deck-item-title">{item.title || item.text}</span>
                        {item.location && <span className="deck-item-loc">LOC // {item.location}</span>}
                      </div>
                    </div>

                    <div className="deck-item-right">
                      <span className={`deck-type-badge ${badgeClass}`}>{badgeLabel}</span>
                      {!isCalendar && !isMission && (
                        <button
                          className="deck-item-del-btn"
                          onClick={(e) => handleDeleteDirective(e, item.id)}
                          title="Delete directive"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* Inline Quick-Add Directive Bar */}
          <div className="deck-input-dock">
            <span className="input-dock-prompt">+</span>
            <input
              type="text"
              className="deck-inline-input"
              placeholder="Add directive... (Press Enter)"
              value={newDirectiveText}
              onChange={(e) => setNewDirectiveText(e.target.value)}
              onKeyDown={handleAddDirective}
              disabled={isAddingDirective}
            />
          </div>
        </div>
      )}

      {/* ================= DECK 2: DISPATCHES (EMAIL) ================= */}
      {activeDeck === 'dispatches' && (
        <div className="deck-content-pane">
          <div className="deck-header-controls">
            <div className="deck-filter-pills">
              <button
                className={`filter-pill ${emailTab === 'inbox' ? 'active' : ''}`}
                onClick={() => setEmailTab('inbox')}
              >
                INBOX {unreadCount > 0 ? `(${unreadCount})` : ''}
              </button>
              <button
                className={`filter-pill ${emailTab === 'sent' ? 'active' : ''}`}
                onClick={() => setEmailTab('sent')}
              >
                SENT
              </button>
            </div>
            <button className="deck-sync-btn" onClick={fetchEmails} title="Refresh Gmail dispatches">
              ⟳
            </button>
          </div>

          <div className="deck-items-list">
            {(emailTab === 'inbox' ? emails : sentEmails).length === 0 ? (
              <div className="deck-empty-state">
                <span className="empty-symbol">[0]</span>
                <span className="empty-text">NO DISPATCHES FOUND</span>
                <span className="empty-sub">Say 'check my email' to fetch new dispatches</span>
              </div>
            ) : (
              (emailTab === 'inbox' ? emails : sentEmails).map((mail, idx) => (
                <div key={idx} className="dispatch-item">
                  <div className="dispatch-header">
                    <span className="dispatch-from">{mail.from || mail.to || 'Unknown'}</span>
                    <span className="dispatch-date">{mail.date || ''}</span>
                  </div>
                  <div className="dispatch-subject">{mail.subject || 'No Subject'}</div>
                  {mail.snippet && <div className="dispatch-snippet">{mail.snippet}</div>}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ================= DECK 3: AUTONOMOUS MISSIONS ================= */}
      {activeDeck === 'missions' && (
        <div className="deck-content-pane">
          <div className="deck-header-controls">
            <span className="deck-pane-title">AUTONOMOUS MISSIONS</span>
            <button className="deck-sync-btn" onClick={fetchMissions} title="Refresh Missions">
              ⟳
            </button>
          </div>

          <div className="deck-items-list">
            {missions.length === 0 ? (
              <div className="deck-empty-state">
                <span className="empty-symbol">[--]</span>
                <span className="empty-text">NO ACTIVE MISSIONS</span>
                <span className="empty-sub">Propose high-level objectives or goals to activate</span>
              </div>
            ) : (
              missions.map((m) => (
                <div key={m.id} className="mission-card">
                  <div className="mission-card-header">
                    <span className="mission-id">#{m.id}</span>
                    <span className={`mission-status-pill ${m.status}`}>{m.status}</span>
                  </div>
                  <div className="mission-title">{m.title}</div>
                  <div className="mission-objective">{m.objective}</div>
                  <div className="mission-progress-bar">
                    <div
                      className="mission-progress-fill"
                      style={{ width: `${m.progress_percentage || 0}%` }}
                    />
                  </div>
                  <div className="mission-stats-row">
                    <span>PROGRESS: {m.progress_percentage || 0}%</span>
                    <span>{m.completed_task_count || 0}/{m.task_count || 0} TASKS</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </aside>
  )
}
