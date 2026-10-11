import React, { useState, useEffect } from 'react'
import './SystemVitals.css'
import MiniCalendar from './MiniCalendar'

export default function SystemVitals({ isConnected = true, onOpenFullCalendar, onExecuteCommand }) {
  const [vitals, setVitals] = useState({
    cpu_pct: 12,
    ram_pct: 42,
    ram_used_gb: 6.7,
    ram_total_gb: 16.0,
    uptime_seconds: 14500,
    commands_today: 18,
    tool_calls_today: 123,
    weather: {
      temp: '28°C',
      condition: 'CLEAR SKY',
      humidity: '58%',
      pressure: '1012 hPa',
      location: 'WORKSHOP // NEW DELHI'
    },
    sentinel: { active: true },
    handsfree: { active: false },
    model: 'nvidia/nemotron-3-super-120b-a12b',
    provider: 'NVIDIA NIM'
  })

  const [activeAction, setActiveAction] = useState(null)

  useEffect(() => {
    let timer

    const fetchVitals = async () => {
      if (window.jarvis?.getVitals) {
        try {
          const data = await window.jarvis.getVitals()
          if (data && typeof data === 'object' && !Array.isArray(data)) {
            setVitals(prev => ({
              ...prev,
              ...data,
              weather: data.weather || prev.weather,
              sentinel: data.sentinel || prev.sentinel,
              handsfree: data.handsfree !== undefined ? data.handsfree : prev.handsfree
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

  const triggerAction = (command, actionKey) => {
    setActiveAction(actionKey)
    setTimeout(() => setActiveAction(null), 1200)

    if (onExecuteCommand) {
      onExecuteCommand(command)
    } else if (window.jarvis?.sendSlashCommand) {
      window.jarvis.sendSlashCommand(command)
    } else if (window.jarvis?.sendMessage) {
      window.jarvis.sendMessage(command)
    }
  }

  return (
    <aside className="vitals-panel">
      {/* 1. Core Hardware Vitals */}
      <div className="vitals-section">
        <div className="vitals-header">
          <span>SYSTEM VITALS</span>
          <span className="vitals-tag">STARK HUD</span>
        </div>
        
        <div className="vital-item">
          <div className="vital-label">
            <span>CPU UTILIZATION</span>
            <span className="vital-val">{Math.round(vitals.cpu_pct || 0)}%</span>
          </div>
          <div className="progress-track">
            <div 
              className="progress-fill cpu-bar" 
              style={{ width: `${Math.min(100, Math.max(0, vitals.cpu_pct || 0))}%` }} 
            />
          </div>
        </div>

        <div className="vital-item">
          <div className="vital-label">
            <span>MEMORY USAGE</span>
            <span className="vital-val">
              {vitals.ram_used_gb ? `${vitals.ram_used_gb}G / ` : ''}
              {Math.round(vitals.ram_pct || 0)}%
            </span>
          </div>
          <div className="progress-track">
            <div 
              className="progress-fill ram-bar" 
              style={{ width: `${Math.min(100, Math.max(0, vitals.ram_pct || 0))}%` }} 
            />
          </div>
        </div>

        <div className="vital-item text-item">
          <span className="vital-title">UPTIME</span>
          <span className="vital-text-val">{formatUptime(vitals.uptime_seconds)}</span>
        </div>
      </div>

      {/* 2. Session Metrics & Neural Telemetry */}
      <div className="vitals-section">
        <div className="vitals-header">
          <span>TELEMETRY</span>
          <span className="vitals-tag">MK 5.8</span>
        </div>

        <div className="telemetry-box">
          <div className="telemetry-row">
            <span className="telemetry-label">COMMANDS</span>
            <span className="telemetry-val">{vitals.commands_today ?? 0}</span>
          </div>
          <div className="telemetry-row">
            <span className="telemetry-label">TOOL SUITE</span>
            <span className="telemetry-val highlight">{vitals.tool_calls_today ?? 123} READY</span>
          </div>
          <div className="telemetry-row provider-row">
            <span className="telemetry-label">NEURAL LINK</span>
            <span className="telemetry-val provider-val">120B MoE // NIM</span>
          </div>
        </div>
      </div>

      {/* 3. STARK TACTICAL GADGET BAY (Fills the gap between sessions and calendar!) */}
      <div className="vitals-section gadgets-bay">
        <div className="vitals-header">
          <span>TACTICAL GADGETS</span>
          <span className="vitals-tag live-dot">● LIVE</span>
        </div>

        {/* Gadget A: Atmospheric & Weather Sensor */}
        <div className="gadget-card weather-gadget">
          <div className="gadget-row">
            <span className="gadget-icon">//</span>
            <span className="gadget-weather-temp">{vitals.weather?.temp || '28°C'}</span>
            <span className="gadget-weather-cond">{vitals.weather?.condition || 'CLEAR SKY'}</span>
          </div>
          <div className="gadget-sub-row">
            <span>HUMIDITY: {vitals.weather?.humidity || '58%'}</span>
            <span className="divider-sep">•</span>
            <span>BARO: {vitals.weather?.pressure || '1012 hPa'}</span>
          </div>
        </div>

        {/* Gadget B: Tactical Macro Matrix (4 One-Click Actions) */}
        <div className="gadget-matrix-grid">
          <button
            type="button"
            className={`gadget-btn ${activeAction === 'briefing' ? 'active-pulse' : ''}`}
            onClick={() => triggerAction('/briefing', 'briefing')}
            title="Launch Tony Stark Morning Briefing (Weather, vitals, directives)"
          >
            <span className="gadget-btn-icon">[BRF]</span>
            <span className="gadget-btn-text">BRIEFING</span>
          </button>

          <button
            type="button"
            className={`gadget-btn ${activeAction === 'sentinel' ? 'active-pulse' : ''}`}
            onClick={() => triggerAction('/copilot', 'sentinel')}
            title="Autonomous Code Sentinel Co-Pilot (Syntax & conflict detector)"
          >
            <span className="gadget-btn-icon">[SNT]</span>
            <span className="gadget-btn-text">SENTINEL</span>
          </button>

          <button
            type="button"
            className={`gadget-btn ${activeAction === 'overdrive' ? 'active-pulse' : ''}`}
            onClick={() => triggerAction('/protocol overdrive', 'overdrive')}
            title="Protocol Overdrive: LLM Warmup & Latency Prewarm"
          >
            <span className="gadget-btn-icon">[OVD]</span>
            <span className="gadget-btn-text">OVERDRIVE</span>
          </button>

          <button
            type="button"
            className={`gadget-btn ${activeAction === 'screen' ? 'active-pulse' : ''}`}
            onClick={() => triggerAction('/screen', 'screen')}
            title="Cross-Modal Vision: Capture & inspect desktop screen"
          >
            <span className="gadget-btn-icon">[VIS]</span>
            <span className="gadget-btn-text">VISION</span>
          </button>
        </div>

        {/* Gadget C: Voice Radar & Acoustic Pulse */}
        <div className="gadget-card acoustic-gadget">
          <div className="acoustic-status-row">
            <span className={`acoustic-indicator ${vitals.handsfree?.active ? 'armed' : 'idle'}`}></span>
            <span className="acoustic-title">
              {vitals.handsfree?.active ? "RADAR: 'HEY JARVIS' ARMED" : "RADAR: PUSH-TO-TALK"}
            </span>
          </div>
          <div className="acoustic-wave-visualizer">
            <span className="wave-bar w1"></span>
            <span className="wave-bar w2"></span>
            <span className="wave-bar w3"></span>
            <span className="wave-bar w4"></span>
            <span className="wave-bar w5"></span>
            <span className="wave-bar w6"></span>
            <span className="wave-bar w7"></span>
          </div>
        </div>
      </div>

      {/* 4. Mini Calendar & Schedule (Docked cleanly below gadgets) */}
      <div className="vitals-calendar-dock">
        <MiniCalendar onOpenFullCalendar={onOpenFullCalendar} />
      </div>
    </aside>
  )
}
