import React, { useState, useRef, useEffect } from 'react'
import './InputBar.css'

export default function InputBar({ onSend, currentSessionId, isHandsFree, onToggleHandsFree, onTriggerVision }) {
  const [text, setText] = useState('')
  const inputRef = useRef(null)

  const focusInput = () => {
    if (inputRef.current) {
      inputRef.current.focus()
    }
  }

  useEffect(() => {
    focusInput()

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

  useEffect(() => {
    focusInput()
    const timer = setTimeout(focusInput, 50)
    const raf = requestAnimationFrame(focusInput)
    return () => {
      clearTimeout(timer)
      cancelAnimationFrame(raf)
    }
  }, [currentSessionId])

  const handleContainerClick = () => {
    focusInput()
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
        placeholder={isHandsFree ? "Say 'Hey JARVIS' or type a command..." : "Type a command or ask JARVIS..."}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        autoFocus
      />
      <div className="input-action-buttons">
        <button
          type="button"
          className="input-action-btn vision-btn"
          onClick={(e) => { e.stopPropagation(); onTriggerVision && onTriggerVision(); }}
          title="Screen Vision: Capture & inspect desktop screen"
        >
          📷
        </button>
        <button
          type="button"
          className={`input-action-btn handsfree-btn ${isHandsFree ? 'active' : ''}`}
          onClick={(e) => { e.stopPropagation(); onToggleHandsFree && onToggleHandsFree(); }}
          title={isHandsFree ? "Hands-Free Mode: ACTIVE ('Hey JARVIS') - Click to disable" : "Hands-Free Mode: OFF - Click to enable"}
        >
          🎙️
          {isHandsFree && <span className="handsfree-dot"></span>}
        </button>
      </div>
      <span className="send-hint">ENTER TO SEND</span>
    </div>
  )
}
