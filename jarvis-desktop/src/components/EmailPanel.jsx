import React, { useState, useEffect } from 'react'
import './EmailPanel.css'

export default function EmailPanel({ isConnected = true, lastStateUpdate = null }) {
  const [emails, setEmails] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [flashing, setFlashing] = useState(false)

  // Initial load on mount or connection
  useEffect(() => {
    if (isConnected && window.jarvis?.checkEmail) {
      window.jarvis.checkEmail()
    }
  }, [isConnected])

  // Listen for real-time WebSocket state_update events for domain "email"
  useEffect(() => {
    if (!lastStateUpdate) return
    const { domain, payload } = lastStateUpdate
    if (domain === 'email') {
      if (payload && Array.isArray(payload.emails)) {
        setEmails(payload.emails)
        setUnreadCount(payload.unread_count ?? payload.emails.length)
      }
      setFlashing(true)
      const timer = setTimeout(() => setFlashing(false), 1600)
      return () => clearTimeout(timer)
    }
  }, [lastStateUpdate])

  const handleManualRefresh = () => {
    if (window.jarvis?.checkEmail) {
      window.jarvis.checkEmail()
    }
  }

  return (
    <div className={`email-panel-container ${flashing ? 'state-flash-highlight' : ''}`}>
      <div className="email-panel-header">
        <span className="email-panel-title">GMAIL INBOX</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span className="email-unread-badge">
            {unreadCount} UNREAD
          </span>
          <button className="email-refresh-btn" onClick={handleManualRefresh} title="Refresh Inbox">
            ↻
          </button>
        </div>
      </div>

      <div className="email-card-list">
        {emails.length === 0 ? (
          <div className="email-empty-state">
            <span className="email-empty-icon">✉</span>
            <span>NO UNREAD EMAILS CARDS</span>
            <span className="email-empty-sub">Ask "check my email" to update inbox</span>
          </div>
        ) : (
          emails.map((item, idx) => {
            const urgencyClass = (item.urgency || 'normal').toLowerCase()
            return (
              <div key={item.id || idx} className="email-card">
                <div className="email-card-header">
                  <span className="email-sender">{item.sender || 'Unknown Sender'}</span>
                  <span className={`email-urgency-tag ${urgencyClass}`}>
                    {item.urgency ? item.urgency.toUpperCase() : 'NORMAL'}
                  </span>
                </div>
                <div className="email-subject">{item.subject || 'No Subject'}</div>
                {item.snippet && (
                  <div className="email-snippet">{item.snippet}</div>
                )}
                {item.date && (
                  <div className="email-date">{item.date}</div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
