import React, { useEffect, useRef, useState } from 'react'
import './ChatLog.css'

/**
 * Checks if a code snippet represents a git or patch diff.
 */
function isDiffContent(code, lang) {
  if (lang && lang.toLowerCase() === 'diff') return true
  if (code.includes('diff --git') || code.includes('--- a/') || code.includes('+++ b/')) return true
  if (/^@@ -\d+,\d+ \+\d+,\d+ @@/m.test(code)) return true
  return false
}

/**
 * Interactive Code Block Component with Copy and Diff Inspection buttons.
 */
function CodeBlock({ code, language = '', onOpenDiff }) {
  const [copied, setCopied] = useState(false)
  const isDiff = isDiffContent(code, language)

  const handleCopy = (e) => {
    e.stopPropagation()
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(code).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
    }
  }

  const handleInspectDiff = (e) => {
    e.stopPropagation()
    if (onOpenDiff) {
      onOpenDiff(code)
    }
  }

  const displayLang = (language || (isDiff ? 'DIFF' : 'CODE')).toUpperCase()

  return (
    <div className={`chat-code-block ${isDiff ? 'diff-mode' : ''}`}>
      <div className="code-block-header">
        <span className="code-lang-label">
          {isDiff && <span className="diff-badge-icon">±</span>}
          {displayLang}
        </span>
        <div className="code-header-actions">
          {isDiff && onOpenDiff && (
            <button
              type="button"
              className="code-action-btn inspect-diff-btn"
              onClick={handleInspectDiff}
              title="Open in Stark Visual Diff Inspector"
            >
              INSPECT DIFF
            </button>
          )}
          <button
            type="button"
            className="code-action-btn copy-btn"
            onClick={handleCopy}
            title="Copy code to clipboard"
          >
            {copied ? 'COPIED' : 'COPY'}
          </button>
        </div>
      </div>
      <pre className="code-block-pre">
        <code>{code}</code>
      </pre>
    </div>
  )
}

/**
 * Formats inline text with bold, inline code, and lists.
 */
function FormattedInlineText({ text }) {
  if (!text) return null

  // Split into lines to format lists and paragraphs
  const lines = text.split('\n')

  return (
    <div className="chat-text-flow">
      {lines.map((line, lIdx) => {
        // Bullet list
        const isBullet = /^[\s]*[-•*]\s+/.test(line)
        const isNumbered = /^[\s]*\d+\.\s+/.test(line)
        const isHeader = /^#{1,4}\s+/.test(line)

        let processedLine = line
        let lineClass = 'text-line'
        if (isBullet) {
          lineClass = 'text-line bullet-item'
          processedLine = line.replace(/^[\s]*[-•*]\s+/, '')
        } else if (isNumbered) {
          lineClass = 'text-line numbered-item'
        } else if (isHeader) {
          lineClass = 'text-line header-item'
          processedLine = line.replace(/^#{1,4}\s+/, '')
        }

        // Parse inline code `code` and bold **bold**
        const tokens = []
        let lastIdx = 0
        const inlineRegex = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g
        let match

        while ((match = inlineRegex.exec(processedLine)) !== null) {
          if (match.index > lastIdx) {
            tokens.push({ type: 'text', val: processedLine.slice(lastIdx, match.index) })
          }
          const raw = match[0]
          if (raw.startsWith('`') && raw.endsWith('`')) {
            tokens.push({ type: 'inline-code', val: raw.slice(1, -1) })
          } else if (raw.startsWith('**') && raw.endsWith('**')) {
            tokens.push({ type: 'bold', val: raw.slice(2, -2) })
          } else if (raw.startsWith('*') && raw.endsWith('*')) {
            tokens.push({ type: 'italic', val: raw.slice(1, -1) })
          }
          lastIdx = match.index + raw.length
        }
        if (lastIdx < processedLine.length) {
          tokens.push({ type: 'text', val: processedLine.slice(lastIdx) })
        }

        return (
          <div key={lIdx} className={lineClass}>
            {isBullet && <span className="bullet-point">▸</span>}
            {tokens.map((token, tIdx) => {
              if (token.type === 'inline-code') {
                return <code key={tIdx} className="chat-inline-code">{token.val}</code>
              }
              if (token.type === 'bold') {
                return <strong key={tIdx} className="chat-bold">{token.val}</strong>
              }
              if (token.type === 'italic') {
                return <em key={tIdx} className="chat-italic">{token.val}</em>
              }
              return <span key={tIdx}>{token.val}</span>
            })}
          </div>
        )
      })}
    </div>
  )
}

/**
 * Message Body Renderer that interleaves text and fenced code blocks.
 */
function MessageContent({ text, onOpenDiff }) {
  if (!text) return null

  // Match fenced code blocks
  const parts = []
  const fenceRegex = /```([a-zA-Z0-9_-]+)?\r?\n([\s\S]*?)```/g
  let lastIndex = 0
  let match

  while ((match = fenceRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({
        type: 'text',
        content: text.slice(lastIndex, match.index)
      })
    }
    parts.push({
      type: 'code',
      language: match[1] || '',
      content: match[2]
    })
    lastIndex = match.index + match[0].length
  }

  if (lastIndex < text.length) {
    parts.push({
      type: 'text',
      content: text.slice(lastIndex)
    })
  }

  return (
    <div className="message-content-wrapper">
      {parts.map((part, idx) => {
        if (part.type === 'code') {
          return (
            <CodeBlock
              key={idx}
              code={part.content}
              language={part.language}
              onOpenDiff={onOpenDiff}
            />
          )
        }
        return <FormattedInlineText key={idx} text={part.content} />
      })}
    </div>
  )
}

export default function ChatLog({ messages = [], onOpenDiff, onExecuteCommand }) {
  const bottomRef = useRef(null)
  const hasUserMessages = messages.some(msg => msg.role === 'user')

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="chat-log-container">
      <div className="chat-log-content">
        {!hasUserMessages && (
          <div className="chat-empty-hero">
            <div className="hero-badge">STARK COMMAND DECK // MK 5.9</div>
            <h1 className="hero-title">How may I assist you today, sir?</h1>
            <p className="hero-subtitle">
              High-performance autonomous intelligence, multi-disk orchestration & neural systems integration.
            </p>

            <div className="hero-cards-grid">
              <div 
                className="hero-card" 
                onClick={() => onExecuteCommand && onExecuteCommand('/briefing')}
                title="Execute /briefing"
              >
                <div className="hero-card-header">
                  <span className="hero-card-tag">[BRF]</span>
                  <span className="hero-card-title">Morning Briefing</span>
                </div>
                <div className="hero-card-desc">
                  Atmospheric weather, hardware vitals, calendar directives & debrief.
                </div>
              </div>

              <div 
                className="hero-card" 
                onClick={() => onExecuteCommand && onExecuteCommand('/screen')}
                title="Execute /screen"
              >
                <div className="hero-card-header">
                  <span className="hero-card-tag">[VIS]</span>
                  <span className="hero-card-title">Screen Vision</span>
                </div>
                <div className="hero-card-desc">
                  Capture desktop screen and inspect with multimodal neural vision.
                </div>
              </div>

              <div 
                className="hero-card" 
                onClick={() => onExecuteCommand && onExecuteCommand('Inspect git status and recent changes across the workspace')}
                title="Inspect Git Status"
              >
                <div className="hero-card-header">
                  <span className="hero-card-tag">[GIT]</span>
                  <span className="hero-card-title">Git Debrief</span>
                </div>
                <div className="hero-card-desc">
                  Inspect modified files, staged changes & active branch telemetry.
                </div>
              </div>

              <div 
                className="hero-card" 
                onClick={() => onExecuteCommand && onExecuteCommand('/copilot')}
                title="Toggle Code Sentinel"
              >
                <div className="hero-card-header">
                  <span className="hero-card-tag">[SNT]</span>
                  <span className="hero-card-title">Code Sentinel</span>
                </div>
                <div className="hero-card-desc">
                  Autonomous real-time syntax anomaly and merge conflict detector.
                </div>
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, index) => {
          const isAlert = msg.isAlert
          const alertType = msg.alertType ? ` [${msg.alertType.toUpperCase()}]` : ''

          let headerLabel = 'USER'
          if (isAlert) {
            headerLabel = `PROACTIVE ALERT${alertType}`
          } else if (msg.role === 'jarvis') {
            headerLabel = 'JARVIS // MK 5.9'
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

              {/* Tool Calls Badges */}
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div className="tool-calls-container">
                  {msg.toolCalls.map((tc, i) => {
                    const isDiffTool = tc.name === 'git_diff' || tc.name === 'inspect_and_edit_archive'
                    return (
                      <div key={i} className="tool-call-badge">
                        <span className="tool-icon">&gt;</span>
                        <span className="tool-text">
                          TOOL EXECUTED: <strong>{tc.name}</strong>
                        </span>
                        {isDiffTool && onOpenDiff && (
                          <button
                            type="button"
                            className="tool-diff-trigger-btn"
                            onClick={() => onOpenDiff()}
                            title="Inspect changes in Diff Viewer"
                          >
                            VIEW DIFF
                          </button>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Formatted Message Body */}
              <div className="chat-message-body">
                <MessageContent text={msg.text} onOpenDiff={onOpenDiff} />
              </div>
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
