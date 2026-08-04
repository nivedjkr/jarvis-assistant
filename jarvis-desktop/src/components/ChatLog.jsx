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
        const borderColor = isAlert ? '#00D9FF' : undefined
        
        return (
          <div
            key={index}
            className={`chat-message ${msg.role}`}
            style={isAlert ? { borderLeft: `2px solid ${borderColor}`, paddingLeft: '10px' } : {}}
          >
            <div className="chat-message-header">
              {isAlert
                ? `⚡ PROACTIVE ALERT${alertType}`
                : msg.role === 'jarvis' ? 'JARVIS' : 'You'
              } · {msg.timestamp}
            </div>

            {/* Display tool execution steps if present */}
            {msg.toolCalls && msg.toolCalls.length > 0 && (
              <div style={{ marginBottom: '6px' }}>
                {msg.toolCalls.map((tc, i) => (
                  <div key={i} style={{
                    fontSize: '11px',
                    fontFamily: 'Consolas, monospace',
                    color: 'rgba(0, 217, 255, 0.85)',
                    background: 'rgba(0, 217, 255, 0.05)',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    margin: '2px 0',
                    border: '1px solid rgba(0, 217, 255, 0.15)'
                  }}>
                    ⚙️ Executed tool: <strong>{tc.name}</strong>
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
