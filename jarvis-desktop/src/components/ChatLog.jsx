import React, { useEffect, useRef } from 'react'
import './ChatLog.css'

export default function ChatLog({ messages = [] }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="chat-log-container">
      {messages.map((msg, index) => {
        const isAlert = msg.isAlert
        const alertType = msg.alertType ? ` [${msg.alertType.toUpperCase()}]` : ''
        
        let headerLabel = 'USER'
        if (isAlert) {
          headerLabel = `PROACTIVE ALERT${alertType}`
        } else if (msg.role === 'jarvis') {
          headerLabel = 'JARVIS'
        }

        return (
          <div
            key={index}
            className={`chat-message ${msg.role} ${isAlert ? 'alert-msg' : ''}`}
          >
            <div className="chat-message-header">
              <span className="who-label">{headerLabel}</span>
              <span className="divider-slash">//</span>
              <span className="time-label">{msg.timestamp}</span>
            </div>

            {msg.toolCalls && msg.toolCalls.length > 0 && (
              <div className="tool-calls-container">
                {msg.toolCalls.map((tc, i) => (
                  <div key={i} className="tool-call-badge">
                    <span className="tool-icon">⚡</span> TOOL EXECUTED: <strong>{tc.name}</strong>
                  </div>
                ))}
              </div>
            )}

            <div className="chat-message-body">
              {msg.text}
            </div>
          </div>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}
