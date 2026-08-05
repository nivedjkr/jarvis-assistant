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

    // Generate ~180 particles for crisp node constellation
    const N = 180
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

      // Spatial grid partitioning (10x10 grid on 600x600 canvas for O(N) connections)
      const GRID_SIZE = 10
      const CELL_SIZE = 60
      const grid = Array.from({ length: GRID_SIZE }, () =>
        Array.from({ length: GRID_SIZE }, () => [])
      )

      // 1. Project 3D particles to 2D screen coordinates and assign to spatial grid cells
      const projected = new Array(particles.length)
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

        projected[i] = { sx, sy, alpha, size }

        const gx = Math.max(0, Math.min(GRID_SIZE - 1, Math.floor(sx / CELL_SIZE)))
        const gy = Math.max(0, Math.min(GRID_SIZE - 1, Math.floor(sy / CELL_SIZE)))
        grid[gx][gy].push(i)

        // Draw particle node
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`
        ctx.beginPath()
        ctx.arc(sx, sy, size, 0, Math.PI * 2)
        ctx.fill()
      }

      // 2. Draw node connections using spatial grid cell proximity (O(N) complexity)
      const maxDistSq = 36 * 36
      ctx.lineWidth = 0.6
      for (let gx = 0; gx < GRID_SIZE; gx++) {
        for (let gy = 0; gy < GRID_SIZE; gy++) {
          const cell = grid[gx][gy]
          if (cell.length === 0) continue

          for (let dx = 0; dx <= 1; dx++) {
            for (let dy = -1; dy <= 1; dy++) {
              if (dx === 0 && dy < 0) continue
              const ngx = gx + dx
              const ngy = gy + dy
              if (ngx < 0 || ngx >= GRID_SIZE || ngy < 0 || ngy >= GRID_SIZE) continue

              const neighborCell = grid[ngx][ngy]
              for (let i = 0; i < cell.length; i++) {
                const idxA = cell[i]
                const pA = projected[idxA]
                const startJ = (ngx === gx && ngy === gy) ? i + 1 : 0

                for (let j = startJ; j < neighborCell.length; j++) {
                  const idxB = neighborCell[j]
                  const pB = projected[idxB]

                  const distSq = (pA.sx - pB.sx) ** 2 + (pA.sy - pB.sy) ** 2
                  if (distSq < maxDistSq) {
                    const lineAlpha = (1 - Math.sqrt(distSq) / 36) * Math.min(pA.alpha, pB.alpha) * 0.35
                    if (lineAlpha > 0.02) {
                      ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${lineAlpha})`
                      ctx.beginPath()
                      ctx.moveTo(pA.sx, pA.sy)
                      ctx.lineTo(pB.sx, pB.sy)
                      ctx.stroke()
                    }
                  }
                }
              }
            }
          }
        }
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

