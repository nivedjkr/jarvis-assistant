import React, { useState, useEffect } from 'react'
import './MiniCalendar.css'

export default function MiniCalendar({ onSelectDate, onOpenFullCalendar }) {
  const [currentDate, setCurrentDate] = useState(new Date())
  const [events, setEvents] = useState([])

  const fetchEvents = async () => {
    try {
      if (window.jarvis?.getCalendarEvents) {
        const data = await window.jarvis.getCalendarEvents()
        if (Array.isArray(data)) setEvents(data)
      } else {
        const res = await fetch('http://127.0.0.1:8765/calendar/events')
        if (res.ok) {
          const data = await res.json()
          if (Array.isArray(data)) setEvents(data)
        }
      }
    } catch (e) {
      console.log('Error fetching mini calendar events:', e)
    }
  }

  useEffect(() => {
    fetchEvents()
    const interval = setInterval(fetchEvents, 30000)
    return () => clearInterval(interval)
  }, [])

  const year = currentDate.getFullYear()
  const month = currentDate.getMonth()

  const monthNames = [
    'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
    'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'
  ]

  const prevMonth = (e) => {
    e.stopPropagation()
    setCurrentDate(new Date(year, month - 1, 1))
  }

  const nextMonth = (e) => {
    e.stopPropagation()
    setCurrentDate(new Date(year, month + 1, 1))
  }

  const firstDayOfMonth = new Date(year, month, 1)
  const lastDayOfMonth = new Date(year, month + 1, 0)
  
  let startDayOfWeek = firstDayOfMonth.getDay() - 1
  if (startDayOfWeek === -1) startDayOfWeek = 6

  const daysInMonth = lastDayOfMonth.getDate()
  const prevMonthLastDay = new Date(year, month, 0).getDate()

  const gridCells = []

  for (let i = startDayOfWeek - 1; i >= 0; i--) {
    const d = prevMonthLastDay - i
    gridCells.push({ date: new Date(year, month - 1, d), isCurrentMonth: false, dayNum: d })
  }

  for (let d = 1; d <= daysInMonth; d++) {
    gridCells.push({ date: new Date(year, month, d), isCurrentMonth: true, dayNum: d })
  }

  const remaining = (gridCells.length <= 35 ? 35 : 42) - gridCells.length
  for (let d = 1; d <= remaining; d++) {
    gridCells.push({ date: new Date(year, month + 1, d), isCurrentMonth: false, dayNum: d })
  }

  const today = new Date()
  const isToday = (cellDate) => {
    return cellDate.getFullYear() === today.getFullYear() &&
           cellDate.getMonth() === today.getMonth() &&
           cellDate.getDate() === today.getDate()
  }

  const hasEvent = (cellDate) => {
    const y = cellDate.getFullYear()
    const m = cellDate.getMonth()
    const d = cellDate.getDate()

    return events.some(ev => {
      if (!ev.start) return false
      const evDate = new Date(ev.start)
      return evDate.getFullYear() === y && evDate.getMonth() === m && evDate.getDate() === d
    })
  }

  return (
    <div className="mini-calendar-container">
      <div className="mini-calendar-header">
        <div className="mini-title">
          <span>📅 SCHEDULE</span>
          <span className="mini-month-label">{monthNames[month]} {year}</span>
        </div>
        <div className="mini-controls">
          <button className="mini-nav-btn" onClick={prevMonth}>‹</button>
          <button className="mini-nav-btn" onClick={nextMonth}>›</button>
          {onOpenFullCalendar && (
            <button className="mini-expand-btn" onClick={onOpenFullCalendar} title="Open Full Month View">
              ⛶
            </button>
          )}
        </div>
      </div>

      <div className="mini-calendar-grid">
        {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((day, idx) => (
          <div key={idx} className="mini-grid-head">{day}</div>
        ))}

        {gridCells.map((cell, idx) => {
          const cellIsToday = isToday(cell.date)
          const cellHasEvent = hasEvent(cell.date)

          return (
            <div
              key={idx}
              className={`mini-grid-cell ${!cell.isCurrentMonth ? 'other-month' : ''} ${cellIsToday ? 'today' : ''} ${cellHasEvent ? 'event' : ''}`}
              onClick={() => onSelectDate && onSelectDate(cell.date)}
            >
              <span>{cell.dayNum}</span>
              {cellHasEvent && <div className="mini-event-dot" />}
            </div>
          )
        })}
      </div>
    </div>
  )
}
