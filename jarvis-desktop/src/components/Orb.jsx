import React, { useEffect, useRef } from 'react'

const STATE_CONFIGS = {
  idle: { speed: 0.003, jitter: 2, r: 140, g: 120, b: 200 },
  thinking: { speed: 0.012, jitter: 14, r: 167, g: 139, b: 250 },
  speaking: { speed: 0.007, jitter: 6, r: 217, g: 70, b: 168 }
}

const statusText = {
  idle: 'IDLE',
  listening: 'LISTENING . . .',
  thinking: 'PROCESSING',
  speaking: 'SPEAKING'
}

export default function Orb({ state = 'idle' }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  const stateRef = useRef(state)

  useEffect(() => {
    stateRef.current = state
  }, [state])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width = 600
    canvas.height = 600

    // Generate ~900 particles once on mount with uniform sphere distribution
    const N = 900
    const particles = []
    for (let i = 0; i < N; i++) {
      const u = Math.random()
      const v = Math.random()
      const theta = 2 * Math.PI * u
      const phi = Math.acos(2 * v - 1)
      const r = 190 + Math.random() * 20
      const tw = Math.random() * Math.PI * 2
      particles.push({ theta, phi, r, tw })
    }

    let rot = 0

    const draw = () => {
      const currentState = stateRef.current || 'idle'
      const cfg = STATE_CONFIGS[currentState] || STATE_CONFIGS.idle
      const { speed, jitter, r, g, b } = cfg

      rot += speed

      const W = canvas.width
      const H = canvas.height
      const centerX = W / 2
      const centerY = H / 2

      ctx.clearRect(0, 0, W, H)

      // Soft radial glow behind the sphere
      const glow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, 220)
      glow.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.35)`)
      glow.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`)
      ctx.fillStyle = glow
      ctx.beginPath()
      ctx.arc(centerX, centerY, 220, 0, Math.PI * 2)
      ctx.fill()

      // Render 3D particles
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i]
        const t = p.theta + rot
        const rr = p.r + Math.sin(p.tw + rot * 4) * jitter
        const x = rr * Math.sin(p.phi) * Math.cos(t)
        const y = rr * Math.sin(p.phi) * Math.sin(t)
        const z = rr * Math.cos(p.phi)
        const scale = 300 / (300 - z)
        const sx = centerX + x * scale * 0.9
        const sy = centerY + y * scale * 0.9
        const alpha = Math.max(0.08, Math.min(0.9, (z + 220) / 440))
        const size = Math.max(0.4, 1.6 * scale * 0.5)

        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`
        ctx.beginPath()
        ctx.arc(sx, sy, size, 0, Math.PI * 2)
        ctx.fill()
      }

      animRef.current = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      if (animRef.current) {
        cancelAnimationFrame(animRef.current)
      }
    }
  }, [])

  const activeConfig = STATE_CONFIGS[state] || STATE_CONFIGS.idle
  const labelColor = `rgb(${activeConfig.r}, ${activeConfig.g}, ${activeConfig.b})`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
      <canvas
        ref={canvasRef}
        width={600}
        height={600}
        style={{ width: '220px', height: '220px' }}
      />
      <div
        style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: '10px',
          letterSpacing: '0.2em',
          color: labelColor,
          fontWeight: 600,
          textTransform: 'uppercase',
          transition: 'color 0.4s ease'
        }}
      >
        {statusText[state] || 'IDLE'}
      </div>
    </div>
  )
}

