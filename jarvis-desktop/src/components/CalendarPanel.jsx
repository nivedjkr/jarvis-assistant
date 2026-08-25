import React, { useState, useEffect } from 'react'
import './CalendarPanel.css'

export default function CalendarPanel({ isOpen, onClose }) {
  const [currentDate, setCurrentDate] = useState(new Date())
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedDay, setSelectedDay] = useState(null)
  const [selectedEvents, setSelectedEvents] = useState([])

  const fetchCalendarEvents = async () => {
    setLoading(true)
    try {
      if (window.jarvis?.getCalendarEvents) {
        const data = await window.jarvis.getCalendarEvents()
        if (Array.isArray(data)) {
          setEvents(data)
        }
      } else {
        const res = await fetch('http://127.0.0.1:8765/calendar/events')
        if (res.ok) {
          const data = await res.json()
          if (Array.isArray(data)) {
            setEvents(data)
          }
        }
      }
    } catch (e) {
      console.log('Error fetching Google Calendar events:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen) {
      fetchCalendarEvents()
    }
  }, [isOpen])

  const year = currentDate.getFullYear()
  const month = currentDate.getMonth()

  const monthNames = [
    'JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE',
    'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'
  ]

  const dayNames = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']

  // Month navigation
  const prevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1))
  }

  const nextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1))
  }

  const goToToday = () => {
    setCurrentDate(new Date())
  }

  // Calculate calendar grid dates (Monday start)
  const firstDayOfMonth = new Date(year, month, 1)
  const lastDayOfMonth = new Date(year, month + 1, 0)
  
  let startDayOfWeek = firstDayOfMonth.getDay() - 1
  if (startDayOfWeek === -1) startDayOfWeek = 6 // Sunday -> 6

  const daysInMonth = lastDayOfMonth.getDate()
  
  const prevMonthLastDay = new Date(year, month, 0).getDate()

  const gridCells = []

  // Leading days from previous month
  for (let i = startDayOfWeek - 1; i >= 0; i--) {
    const d = prevMonthLastDay - i
    const cellDate = new Date(year, month - 1, d)
    gridCells.push({ date: cellDate, isCurrentMonth: false, dayNum: d })
  }

  // Days of current month
  for (let d = 1; d <= daysInMonth; d++) {
    const cellDate = new Date(year, month, d)
    gridCells.push({ date: cellDate, isCurrentMonth: true, dayNum: d })
  }

  // Trailing days for next month to fill 35 or 42 grid cells
  const remainingCells = (gridCells.length <= 35 ? 35 : 42) - gridCells.length
  for (let d = 1; d <= remainingCells; d++) {
    const cellDate = new Date(year, month + 1, d)
    gridCells.push({ date: cellDate, isCurrentMonth: false, dayNum: d })
  }

  // Helper to match events to cell date
  const getEventsForDate = (cellDate) => {
    const y = cellDate.getFullYear()
    const m = cellDate.getMonth()
    const d = cellDate.getDate()

    return events.filter(ev => {
      if (!ev.start) return false
      const evDate = new Date(ev.start)
      return evDate.getFullYear() === y && evDate.getMonth() === m && evDate.getDate() === d
    })
  }

  const today = new Date()
  const isToday = (cellDate) => {
    return cellDate.getFullYear() === today.getFullYear() &&
           cellDate.getMonth() === today.getMonth() &&
           cellDate.getDate() === today.getDate()
  }

  const handleCellClick = (cell) => {
    const evs = getEventsForDate(cell.date)
    setSelectedDay(cell.date)
    setSelectedEvents(evs)
  }

  if (!isOpen) return null

  return (
    <aside className="calendar-panel-container">
      <div className="calendar-header">
        <div className="calendar-title-group">
          <span className="calendar-brand-title">GOOGLE CALENDAR</span>
          <span className="calendar-month-display">{monthNames[month]} {year}</span>
        </div>
        <div className="calendar-header-actions">
          <button className="cal-btn-icon" onClick={fetchCalendarEvents} title="Refresh Google Sync">
            {loading ? '⏳' : '🔄'}
          </button>
          <button className="cal-btn-icon" onClick={onClose} title="Close Calendar">✕</button>
        </div>
      </div>

      {/* Navigation Toolbar */}
      <div className="calendar-toolbar">
        <button className="cal-btn" onClick={prevMonth}>‹ PREV</button>
        <button className="cal-btn today-btn" onClick={goToToday}>TODAY</button>
        <button className="cal-btn" onClick={nextMonth}>NEXT ›</button>
      </div>

      {/* Calendar Month Grid */}
      <div className="calendar-grid">
        {dayNames.map(day => (
          <div key={day} className="calendar-day-header">{day}</div>
        ))}

        {gridCells.map((cell, idx) => {
          const dayEvents = getEventsForDate(cell.date)
          const cellIsToday = isToday(cell.date)

          return (
            <div
              key={idx}
              className={`calendar-cell ${!cell.isCurrentMonth ? 'other-month' : ''} ${cellIsToday ? 'today' : ''} ${dayEvents.length > 0 ? 'has-events' : ''}`}
              onClick={() => handleCellClick(cell)}
            >
              <div className="cell-header">
                <span className="cell-number">{cell.dayNum}</span>
                {cellIsToday && <span className="today-badge">TODAY</span>}
              </div>

              {dayEvents.length > 0 && (
                <div className="cell-events-summary">
                  {dayEvents.slice(0, 2).map((ev, i) => (
                    <div key={i} className="cell-event-pill" title={ev.summary}>
                      {ev.summary}
                    </div>
                  ))}
                  {dayEvents.length > 2 && (
                    <span className="more-events-badge">+{dayEvents.length - 2} more</span>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Selected Day Event Drawer */}
      {selectedDay && (
        <div className="selected-day-modal">
          <div className="day-modal-header">
            <h4>
              📅 {selectedDay.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
            </h4>
            <button className="cal-btn-icon" onClick={() => setSelectedDay(null)}>✕</button>
          </div>
          <div className="day-modal-body">
            {selectedEvents.length === 0 ? (
              <div className="no-events-msg">No Google Calendar events scheduled for this day</div>
            ) : (
              selectedEvents.map((ev, idx) => (
                <div key={idx} className="event-detail-card">
                  <div className="event-detail-title">{ev.summary}</div>
                  <div className="event-detail-time">
                    ⏰ {ev.start ? new Date(ev.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'All Day'}
                    {ev.end ? ` - ${new Date(ev.end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : ''}
                  </div>
                  {ev.location && <div className="event-detail-loc">📍 {ev.location}</div>}
                  {ev.description && <div className="event-detail-desc">{ev.description}</div>}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </aside>
  )
}
