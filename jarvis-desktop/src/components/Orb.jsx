import React from 'react'
import './Orb.css'

const states = {
  idle: {
    barColor: '#00D9FF',
    statusColor: '#0d2e2e',
    statusText: 'IDLE',
    animation: 'idle-pulse',
    duration: '3s',
    maxHeight: 10,
    opacity: 0.2,
    delays: [0, 0.4, 0.8, 1.2, 1.6]
  },
  listening: {
    barColor: '#00D9FF',
    statusColor: '#00D9FF',
    statusText: 'LISTENING . . .',
    animation: 'listen-pulse',
    duration: '0.9s',
    maxHeight: 48,
    opacity: 1,
    delays: [0, 0.15, 0.3, 0.15, 0]
  },
  thinking: {
    barColor: '#006688',
    statusColor: '#006688',
    statusText: 'PROCESSING',
    animation: 'think-pulse',
    duration: '2s',
    maxHeight: 40,
    opacity: 0.7,
    delays: [0, 0.3, 0.6, 0.9, 1.2]
  },
  speaking: {
    barColor: '#00FFFF',
    statusColor: '#00FFFF',
    statusText: 'SPEAKING',
    animation: 'speak-pulse',
    duration: '0.5s',
    maxHeight: 56,
    opacity: 1,
    delays: [0, 0.1, 0.2, 0.1, 0]
  }
}

export default function Orb({ state = 'idle' }) {
  const current = states[state] || states.idle

  return (
    <div className="orb-container">
      <div className="orb-bars">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="orb-bar"
            style={{
              backgroundColor: current.barColor,
              opacity: current.opacity,
              animationName: current.animation,
              animationDuration: current.duration,
              animationDelay: `${current.delays[i]}s`
            }}
          />
        ))}
      </div>
      <div
        className="orb-status"
        style={{ color: current.statusColor }}
      >
        {current.statusText}
      </div>
    </div>
  )
}
