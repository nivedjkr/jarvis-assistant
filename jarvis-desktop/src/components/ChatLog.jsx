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
        const isUltron = msg.alertType?.startsWith('ultron')
        const alertType = msg.alertType ? ` [${msg.alertType.toUpperCase()}]` : ''
        const borderColor = isUltron ? '#FF6B00' : isAlert ? '#00D9FF' : undefined
        
        return (
          <div
            key={index}
            className={`chat-message ${msg.role}`}
            style={isAlert || isUltron ? { borderLeft: `2px solid ${borderColor}`, paddingLeft: '10px' } : {}}
          >
            {isUltron && (
              <div style={{
                fontSize: '10px',
                color: '#FF6B00',
                fontWeight: 'bold',
                letterSpacing: '0.08em',
                marginBottom: '2px',
                fontFamily: 'monospace'
              }}>
                ULTRON
              </div>
            )}
            <div className="chat-message-header" style={isUltron ? { color: '#FF6B00' } : {}}>
              {isUltron
                ? `🚨 ULTRON ALERT${alertType}`
                : isAlert
                ? `⚡ PROACTIVE ALERT${alertType}`
                : msg.role === 'jarvis' ? 'JARVIS' : 'You'
              } · {msg.timestamp}
            </div>

            {/* Display tool execution steps if present */}
            {msg.toolCalls && msg.toolCalls.length > 0 && (
              <div style={{ marginBottom: '6px' }}>
                {msg.toolCalls.map((tc, i) => (
                  <div key={i} style={{
                    fontSize: '10px',
                    color: '#00D9FF',
                    letterSpacing: '0.05em',
                    marginBottom: '3px',
                    fontFamily: 'monospace',
                    opacity: 0.85
                  }}>
                    ◈ {tc.name} → {typeof tc.result === 'string' ? tc.result.slice(0, 70) : JSON.stringify(tc.result).slice(0, 70)}...
                  </div>
                ))}
              </div>
            )}

            <div className="chat-message-text" style={{ whiteSpace: 'pre-wrap' }}>
              {msg.text}
            </div>
          </div>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}
