import React, { useEffect, useRef } from 'react'

export default function Orb({ state = 'idle' }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  const stateRef = useRef(state)
  const pointsRef = useRef([])

  useEffect(() => {
    stateRef.current = state
  }, [state])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const W = (canvas.width = 300)
    const H = (canvas.height = 300)
    const CX = W / 2
    const CY = H / 2

    // Generate ~900 3D points on a sphere using Fibonacci sphere algorithm
    const count = 900
    const phi = Math.PI * (3 - Math.sqrt(5))
    pointsRef.current = Array.from({ length: count }, (_, i) => {
      const y = 1 - (i / (count - 1)) * 2
      const r = Math.sqrt(1 - y * y)
      const theta = phi * i
      return {
        x: Math.cos(theta) * r,
        y: y,
        z: Math.sin(theta) * r,
        phase: Math.random() * Math.PI * 2
      }
    })

    let rotX = 0
    let rotY = 0
    let time = 0

    const draw = () => {
      const currentState = stateRef.current || 'idle'
      time += 0.02

      // Configs per state
      const configs = {
        idle: {
          baseColor: '#a78bfa',
          rotSpeedX: 0.003,
          rotSpeedY: 0.006,
          radius: 90,
          jitter: 0,
          particleSize: 1.4,
          glowAlpha: 0.15
        },
        listening: {
          baseColor: '#00D9FF',
          rotSpeedX: 0.008,
          rotSpeedY: 0.014,
          radius: 105,
          jitter: 0.02,
          particleSize: 1.8,
          glowAlpha: 0.3
        },
        thinking: {
          baseColor: '#6644FF',
          rotSpeedX: 0.015,
          rotSpeedY: 0.025,
          radius: 85,
          jitter: 0.08,
          particleSize: 1.5,
          glowAlpha: 0.25
        },
        speaking: {
          baseColor: '#d946a8',
          rotSpeedX: 0.01,
          rotSpeedY: 0.018,
          radius: 98,
          jitter: 0.03,
          particleSize: 2.0,
          glowAlpha: 0.4
        }
      }

      const cfg = configs[currentState] || configs.idle

      rotX += cfg.rotSpeedX
      rotY += cfg.rotSpeedY

      ctx.fillStyle = '#08080b'
      ctx.fillRect(0, 0, W, H)

      const fov = 260
      const points = pointsRef.current

      // Calculate 3D transformation for points
      const transformed = points.map(pt => {
        let px = pt.x
        let py = pt.y
        let pz = pt.z

        // Add state-specific jitter
        if (cfg.jitter > 0) {
          px += (Math.random() - 0.5) * cfg.jitter
          py += (Math.random() - 0.5) * cfg.jitter
          pz += (Math.random() - 0.5) * cfg.jitter
        }

        // Breathing effect in idle
        let currentRadius = cfg.radius
        if (currentState === 'idle') {
          currentRadius += Math.sin(time * 1.5 + pt.phase) * 3
        }

        // Y-axis rotation
        const x1 = px * Math.cos(rotY) + pz * Math.sin(rotY)
        const z1 = -px * Math.sin(rotY) + pz * Math.cos(rotY)
        const y1 = py

        // X-axis rotation
        const y2 = y1 * Math.cos(rotX) - z1 * Math.sin(rotX)
        const z2 = y1 * Math.sin(rotX) + z1 * Math.cos(rotX)
        const x2 = x1

        // Perspective projection
        const scale = fov / (fov + z2 * currentRadius)
        const screenX = CX + x2 * currentRadius * scale
        const screenY = CY + y2 * currentRadius * scale

        return {
          x: screenX,
          y: screenY,
          z: z2,
          scale: scale,
          rawY: y2
        }
      })

      // Sort points back to front for realistic depth transparency rendering
      transformed.sort((a, b) => a.z - b.z)

      // Center sphere atmospheric glow
      const centerGlow = ctx.createRadialGradient(CX, CY, 10, CX, CY, cfg.radius * 1.2)
      centerGlow.addColorStop(0, cfg.baseColor)
      centerGlow.addColorStop(1, 'transparent')
      ctx.globalAlpha = cfg.glowAlpha
      ctx.fillStyle = centerGlow
      ctx.beginPath()
      ctx.arc(CX, CY, cfg.radius * 1.2, 0, Math.PI * 2)
      ctx.fill()

      // Render 3D sphere particles
      transformed.forEach(p => {
        // Map depth to opacity (front = bright, back = dim)
        const alpha = Math.max(0.1, (p.z + 1) / 2)

        let color = cfg.baseColor
        let pSize = cfg.particleSize * p.scale

        // Speaking state: ripple pulse wave moving along sphere latitude
        if (currentState === 'speaking') {
          const wave = Math.sin(time * 6 - p.rawY * 5)
          if (wave > 0.4) {
            color = '#FFFFFF'
            pSize *= 1.4
          }
        }

        ctx.globalAlpha = alpha * 0.9
        ctx.fillStyle = color
        ctx.beginPath()
        ctx.arc(p.x, p.y, Math.max(0.5, pSize), 0, Math.PI * 2)
        ctx.fill()
      })

      ctx.globalAlpha = 1.0
      animRef.current = requestAnimationFrame(draw)
    }

    draw()

    return () => {
      if (animRef.current) {
        cancelAnimationFrame(animRef.current)
      }
    }
  }, [])

  const statusText = {
    idle: 'IDLE',
    listening: 'LISTENING . . .',
    thinking: 'PROCESSING',
    speaking: 'SPEAKING'
  }

  const statusColors = {
    idle: '#6b6b74',
    listening: '#00D9FF',
    thinking: '#6644FF',
    speaking: '#d946a8'
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
      <canvas
        ref={canvasRef}
        width={300}
        height={300}
        style={{ width: '220px', height: '220px' }}
      />
      <div
        style={{
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: '10px',
          letterSpacing: '0.2em',
          color: statusColors[state] || '#6b6b74',
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
