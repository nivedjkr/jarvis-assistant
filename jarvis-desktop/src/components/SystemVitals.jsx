import React, { useState, useEffect } from 'react'
import './SystemVitals.css'

export default function SystemVitals({ isConnected = true }) {
  const [vitals, setVitals] = useState({
    cpu_pct: 12,
    ram_pct: 42,
    ram_used_gb: 6.7,
    ram_total_gb: 16.0,
    uptime_seconds: 14500,
    commands_today: 18,
    tool_calls_today: 42
  })

  useEffect(() => {
    let timer

    const fetchVitals = async () => {
      if (window.jarvis?.getVitals) {
        try {
          const data = await window.jarvis.getVitals()
          if (data && typeof data === 'object' && !Array.isArray(data)) {
            setVitals(prev => ({
              ...prev,
              ...data
            }))
          }
        } catch (e) {
          // Keep existing vitals on error
        }
      }
    }

    fetchVitals()
    timer = setInterval(fetchVitals, 3000)

    return () => clearInterval(timer)
  }, [isConnected])

  const formatUptime = (totalSec) => {
    if (!totalSec || totalSec <= 0) return '00h 00m'
    const h = Math.floor(totalSec / 3600)
    const m = Math.floor((totalSec % 3600) / 60)
    return `${String(h).padStart(2, '0')}h ${String(m).padStart(2, '0')}m`
  }

  return (
    <aside className="vitals-panel">
      <div className="vitals-section">
        <div className="vitals-header">SYSTEM VITALS</div>
        
        <div className="vital-item">
          <div className="vital-label">
            <span>CPU UTILIZATION</span>
            <span className="vital-val">{Math.round(vitals.cpu_pct || 0)}%</span>
          </div>
          <div className="progress-track">
            <div 
              className="progress-fill" 
              style={{ width: `${Math.min(100, Math.max(0, vitals.cpu_pct || 0))}%` }} 
            />
          </div>
        </div>

        <div className="vital-item">
          <div className="vital-label">
            <span>MEMORY USAGE</span>
            <span className="vital-val">{Math.round(vitals.ram_pct || 0)}%</span>
          </div>
          <div className="progress-track">
            <div 
              className="progress-fill" 
              style={{ width: `${Math.min(100, Math.max(0, vitals.ram_pct || 0))}%` }} 
            />
          </div>
        </div>

        <div className="vital-item text-item">
          <span className="vital-title">UPTIME</span>
          <span className="vital-text-val">{formatUptime(vitals.uptime_seconds)}</span>
        </div>
      </div>

      <div className="vitals-section">
        <div className="vitals-header">SESSIONS TODAY</div>

        <div className="telemetry-box">
          <div className="telemetry-row">
            <span className="telemetry-label">COMMANDS</span>
            <span className="telemetry-val">{vitals.commands_today ?? 0}</span>
          </div>
          <div className="telemetry-row">
            <span className="telemetry-label">TOOL CALLS</span>
            <span className="telemetry-val">{vitals.tool_calls_today ?? 0}</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
