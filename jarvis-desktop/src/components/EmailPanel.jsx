import React, { useState, useEffect } from 'react'
import './EmailPanel.css'

export default function EmailPanel({ isConnected = true, lastStateUpdate = null }) {
  const [activeTab, setActiveTab] = useState('inbox')
  const [emails, setEmails] = useState([])
  const [sentEmails, setSentEmails] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [flashing, setFlashing] = useState(false)

  // Initial load on mount or connection
  useEffect(() => {
    if (isConnected) {
      if (activeTab === 'inbox' && window.jarvis?.checkEmail) {
        window.jarvis.checkEmail()
      } else if (activeTab === 'sent') {
        if (window.jarvis?.getSentEmails) {
          window.jarvis.getSentEmails().then(res => {
            if (res && Array.isArray(res.sent_emails)) {
              setSentEmails(res.sent_emails)
            }
          }).catch(err => console.log('[EMAIL] Error fetching sent emails:', err))
        } else if (window.jarvis?.listSentEmails) {
          window.jarvis.listSentEmails()
        }
      }
    }
  }, [isConnected, activeTab])

  // Listen for real-time WebSocket state_update events for domain "email" / "sent_email"
  useEffect(() => {
    if (!lastStateUpdate) return
    const { domain, payload } = lastStateUpdate
    if (domain === 'email' || domain === 'sent_email') {
      if (payload && Array.isArray(payload.emails)) {
        setEmails(payload.emails)
        setUnreadCount(payload.unread_count ?? payload.emails.length)
      }
      if (payload && Array.isArray(payload.sent_emails)) {
        setSentEmails(payload.sent_emails)
      }
      setFlashing(true)
      const timer = setTimeout(() => setFlashing(false), 1600)
      return () => clearTimeout(timer)
    }
  }, [lastStateUpdate])

  const handleManualRefresh = () => {
    if (activeTab === 'inbox' && window.jarvis?.checkEmail) {
      window.jarvis.checkEmail()
    } else if (activeTab === 'sent') {
      if (window.jarvis?.getSentEmails) {
        window.jarvis.getSentEmails().then(res => {
          if (res && Array.isArray(res.sent_emails)) {
            setSentEmails(res.sent_emails)
          }
        }).catch(err => console.log('[EMAIL] Error fetching sent emails:', err))
      } else if (window.jarvis?.listSentEmails) {
        window.jarvis.listSentEmails()
      }
    }
  }

  const handleDeleteSent = (idx) => {
    if (window.jarvis?.deleteSentEmail) {
      window.jarvis.deleteSentEmail(idx + 1)
    } else if (window.jarvis?.sendSlashCommand) {
      window.jarvis.sendSlashCommand(`/email delete ${idx + 1}`)
    }
  }

  const displayList = activeTab === 'inbox' ? emails : sentEmails

  return (
    <div className={`email-panel-container ${flashing ? 'state-flash-highlight' : ''}`}>
      <div className="email-panel-header">
        <div className="email-tab-group">
          <button 
            className={`email-tab-btn ${activeTab === 'inbox' ? 'active' : ''}`}
            onClick={() => setActiveTab('inbox')}
          >
            INBOX
          </button>
          <button 
            className={`email-tab-btn ${activeTab === 'sent' ? 'active' : ''}`}
            onClick={() => setActiveTab('sent')}
          >
            SENT
          </button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {activeTab === 'inbox' && (
            <span className="email-unread-badge">
              {unreadCount} UNREAD
            </span>
          )}
          <button className="email-refresh-btn" onClick={handleManualRefresh} title="Refresh">
            ↻
          </button>
        </div>
      </div>

      <div className="email-card-list">
        {displayList.length === 0 ? (
          <div className="email-empty-state">
            <span className="email-empty-icon">✉</span>
            <span>{activeTab === 'inbox' ? 'NO UNREAD EMAILS' : 'NO SENT EMAILS'}</span>
            <span className="email-empty-sub">
              {activeTab === 'inbox' ? 'Ask "check my email" to update inbox' : 'Ask "/email sent" to view sent mails'}
            </span>
          </div>
        ) : (
          displayList.map((item, idx) => {
            const urgencyClass = (item.urgency || 'normal').toLowerCase()
            return (
              <div key={item.id || idx} className="email-card">
                <div className="email-card-header">
                  <span className="email-sender">
                    {activeTab === 'inbox' ? (item.sender || 'Unknown Sender') : (`To: ${item.recipient || item.to || 'Unknown'}`)}
                  </span>
                  {activeTab === 'inbox' ? (
                    <span className={`email-urgency-tag ${urgencyClass}`}>
                      {item.urgency ? item.urgency.toUpperCase() : 'NORMAL'}
                    </span>
                  ) : (
                    <button 
                      className="email-delete-btn" 
                      onClick={() => handleDeleteSent(idx)} 
                      title="Delete Sent Email"
                    >
                      ✕ Delete
                    </button>
                  )}
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
