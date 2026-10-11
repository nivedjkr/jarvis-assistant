import React, { useState, useRef, useEffect } from 'react'
import './InputBar.css'

export default function InputBar({ onSend, currentSessionId, isHandsFree, onToggleHandsFree, onTriggerVision }) {
  const [text, setText] = useState('')
  const textareaRef = useRef(null)

  const focusInput = () => {
    if (textareaRef.current) {
      textareaRef.current.focus()
    }
  }

  const resizeTextarea = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      const newHeight = Math.min(Math.max(textareaRef.current.scrollHeight, 24), 160)
      textareaRef.current.style.height = `${newHeight}px`
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
      if (textareaRef.current && e.key.length === 1) {
        textareaRef.current.focus()
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

  const submitMessage = () => {
    const messageText = text.trim()
    if (!messageText) return

    setText('')
    if (textareaRef.current) {
      textareaRef.current.style.height = '24px'
    }

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
      textareaRef.current?.focus()
    }, 50)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submitMessage()
    }
  }

  const handleChange = (e) => {
    setText(e.target.value)
    resizeTextarea()
  }

  return (
    <div className="terminal-input-bar" onClick={focusInput}>
      <div className="input-field-row">
        <span className="prompt-symbol">&gt;</span>
        <textarea
          ref={textareaRef}
          rows={1}
          className="terminal-input-field"
          placeholder={isHandsFree ? "Say 'Hey JARVIS' or type a directive..." : "Ask JARVIS or type a command (e.g. /briefing, /plan)..."}
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          autoFocus
        />
      </div>

      <div className="input-toolbar-row">
        <div className="input-action-buttons">
          <button
            type="button"
            className="input-action-btn briefing-btn"
            onClick={(e) => { e.stopPropagation(); onSend && onSend('/briefing'); }}
            title="Stark Morning Briefing: Atmospheric weather, vitals, directives, and workshop debrief"
          >
            [BRF]
          </button>
          <button
            type="button"
            className="input-action-btn vision-btn"
            onClick={(e) => { e.stopPropagation(); onTriggerVision && onTriggerVision(); }}
            title="Screen Vision: Capture & inspect desktop screen"
          >
            [VIS]
          </button>
          <button
            type="button"
            className={`input-action-btn handsfree-btn ${isHandsFree ? 'active' : ''}`}
            onClick={(e) => { e.stopPropagation(); onToggleHandsFree && onToggleHandsFree(); }}
            title={isHandsFree ? "Hands-Free Mode: ACTIVE ('Hey JARVIS') - Click to disable" : "Hands-Free Mode: OFF - Click to enable"}
          >
            [MIC]
            {isHandsFree && <span className="handsfree-dot"></span>}
          </button>
        </div>

        <div className="input-send-group">
          <span className="send-hint">ENTER ↵</span>
          <button
            type="button"
            className={`send-action-btn ${text.trim() ? 'active' : ''}`}
            disabled={!text.trim()}
            onClick={(e) => { e.stopPropagation(); submitMessage(); }}
            title="Send directive"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="19" x2="12" y2="5" />
              <polyline points="5 12 12 5 19 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
