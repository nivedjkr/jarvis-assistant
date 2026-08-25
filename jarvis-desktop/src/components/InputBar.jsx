import React, { useState, useRef, useEffect } from 'react'
import './InputBar.css'

export default function InputBar({ onSend }) {
  const [text, setText] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleContainerClick = () => {
    inputRef.current?.focus()
  }

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
      
      setTimeout(() => {
        inputRef.current?.focus()
      }, 10)
    }
  }

  return (
    <div className="terminal-input-bar" onClick={handleContainerClick}>
      <span className="prompt-symbol">&gt;</span>
      <input
        ref={inputRef}
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
