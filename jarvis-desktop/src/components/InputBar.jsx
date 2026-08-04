import React, { useState } from 'react'
import './InputBar.css'

export default function InputBar({ onSend }) {
  const [text, setText] = useState('')

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && text.trim()) {
      const messageText = text.trim()
      setText('')
      
      if (onSend) {
        onSend(messageText)
      } else {
        if (messageText.startsWith('/')) {
          if (window.jarvis?.sendSlashCommand) {
            window.jarvis.sendSlashCommand(messageText)
          }
        } else {
          if (window.jarvis?.sendMessage) {
            window.jarvis.sendMessage(messageText)
          }
        }
      }
    }
  }

  return (
    <div className="terminal-input-bar">
      <span className="prompt-symbol">&gt;</span>
      <input
        type="text"
        className="terminal-input-field"
        placeholder="Type a command or ask JARVIS..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        autoFocus
      />
      <span className="send-hint">ENTER TO SEND</span>
    </div>
  )
}
