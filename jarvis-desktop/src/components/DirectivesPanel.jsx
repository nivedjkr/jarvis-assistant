import React, { useState, useEffect } from 'react'
import './DirectivesPanel.css'

export default function DirectivesPanel({ isConnected = true }) {
  const [directives, setDirectives] = useState([
    { id: 1, text: 'Review portfolio AAPL target', completed: false },
    { id: 2, text: 'Backup SQLite memory DB', completed: false },
    { id: 3, text: 'Check internship board updates', completed: false }
  ])

  useEffect(() => {
    let timer

    const fetchDirectives = async () => {
      if (window.jarvis?.getReminders) {
        try {
          const reminders = await window.jarvis.getReminders()
          if (Array.isArray(reminders) && reminders.length > 0) {
            const formatted = reminders.map((r, i) => ({
              id: r.id || i,
              text: r.message || r.text || r.task || 'Pending directive',
              completed: Boolean(r.completed)
            }))
            setDirectives(formatted)
          }
        } catch (e) {
          // Keep existing directives on error
        }
      }
    }

    fetchDirectives()
    timer = setInterval(fetchDirectives, 5000)

    return () => clearInterval(timer)
  }, [isConnected])

  const toggleDirective = (id) => {
    setDirectives(prev =>
      prev.map(item =>
        item.id === id ? { ...item, completed: !item.completed } : item
      )
    )
  }

  return (
    <aside className="directives-panel">
      <div className="directives-header">DIRECTIVES</div>
      
      <div className="directives-list">
        {directives.length === 0 ? (
          <div className="no-directives">NO ACTIVE DIRECTIVES</div>
        ) : (
          directives.map(item => (
            <div
              key={item.id}
              className={`directive-item ${item.completed ? 'completed' : ''}`}
              onClick={() => toggleDirective(item.id)}
            >
              <span className="directive-marker">
                {item.completed ? '◇' : '◆'}
              </span>
              <span className="directive-text">{item.text}</span>
            </div>
          ))
        )}
      </div>
    </aside>
  )
}
