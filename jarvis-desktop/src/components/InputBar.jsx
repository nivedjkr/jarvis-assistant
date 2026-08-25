import React, { useState, useRef, useEffect } from 'react'
import './InputBar.css'

export default function InputBar({ onSend }) {
  const [text, setText] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    // Focus input field immediately when mounted
    inputRef.current?.focus()

    // Global listener to re-focus input box whenever user starts typing outside any form control
    const handleGlobalKeyDown = (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const activeEl = document.activeElement
      if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || activeEl.isContentEditable)) {
        return
      }
      if (inputRef.current && e.key.length === 1) {
        inputRef.current.focus()
      }
    }

    window.addEventListener('keydown', handleGlobalKeyDown)
    return () => window.removeEventListener('keydown', handleGlobalKeyDown)
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
      }, 50)
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
