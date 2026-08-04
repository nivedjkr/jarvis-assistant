import { useEffect, useRef } from 'react'

export default function Orb({ state = 'idle' }) {
  const canvasRef = useRef(null)
  const animRef = useRef(null)
  const nodesRef = useRef([])
  const stateRef = useRef(state)
  
  // Update stateRef when state prop changes
  useEffect(() => {
    stateRef.current = state
  }, [state])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    
    // Canvas size
    const W = canvas.width = 400
    const H = canvas.height = 400
    const CX = W / 2
    const CY = H / 2
    
    // State configs
    const configs = {
      idle: {
        nodeColor: '#00D9FF',
        lineColor: '#00D9FF',
        nodeOpacity: 0.25,
        lineOpacity: 0.08,
        speed: 0.15,
        pulseSpeed: 0.008,
        connectionDist: 80,
        nodeCount: 45,
        nodeSize: 2
      },
      listening: {
        nodeColor: '#00D9FF',
        lineColor: '#00FFFF',
        nodeOpacity: 0.8,
        lineOpacity: 0.3,
        speed: 0.4,
        pulseSpeed: 0.025,
        connectionDist: 100,
        nodeCount: 45,
        nodeSize: 3
      },
      thinking: {
        nodeColor: '#6644FF',
        lineColor: '#4422FF',
        nodeOpacity: 0.6,
        lineOpacity: 0.2,
        speed: 0.25,
        pulseSpeed: 0.015,
        connectionDist: 90,
        nodeCount: 45,
        nodeSize: 2.5
      },
      speaking: {
        nodeColor: '#00FFFF',
        lineColor: '#FFFFFF',
        nodeOpacity: 1.0,
        lineOpacity: 0.4,
        speed: 0.6,
        pulseSpeed: 0.04,
        connectionDist: 120,
        nodeCount: 45,
        nodeSize: 3.5
      }
    }
    
    // Initialize nodes
    const initNodes = (count) => {
      nodesRef.current = Array.from({ length: count }, (_, i) => {
        // Distribute nodes — some clustered near center, 
        // some spread to edges (like Obsidian graph)
        const angle = Math.random() * Math.PI * 2
        const radius = Math.random() < 0.3 
          ? Math.random() * 60   // 30% near center
          : 60 + Math.random() * 130  // 70% spread out
        return {
          x: CX + Math.cos(angle) * radius,
          y: CY + Math.sin(angle) * radius,
          vx: (Math.random() - 0.5) * 0.5,
          vy: (Math.random() - 0.5) * 0.5,
          radius: 1.5 + Math.random() * 2,
          pulseOffset: Math.random() * Math.PI * 2,
          // Some nodes are "hubs" — bigger, more connected
          isHub: Math.random() < 0.1
        }
      })
    }
    
    initNodes(45)
    let time = 0
    
    const draw = () => {
      const cfg = configs[stateRef.current] || configs.idle
      time += cfg.pulseSpeed
      
      // Clear with slight trail effect for glow
      ctx.fillStyle = 'rgba(0, 0, 0, 0.15)'
      ctx.fillRect(0, 0, W, H)
      
      // Update node positions
      nodesRef.current.forEach(node => {
        node.x += node.vx * cfg.speed
        node.y += node.vy * cfg.speed
        
        // Soft boundary — nodes drift back toward canvas
        const margin = 30
        if (node.x < margin) node.vx += 0.05
        if (node.x > W - margin) node.vx -= 0.05
        if (node.y < margin) node.vy += 0.05
        if (node.y > H - margin) node.vy -= 0.05
        
        // Gentle center gravity for idle state
        if (stateRef.current === 'idle') {
          node.vx += (CX - node.x) * 0.0001
          node.vy += (CY - node.y) * 0.0001
        }
        
        // Speed limiting
        const maxSpeed = 0.8
        const speed = Math.sqrt(
          node.vx * node.vx + node.vy * node.vy
        )
        if (speed > maxSpeed) {
          node.vx = (node.vx / speed) * maxSpeed
          node.vy = (node.vy / speed) * maxSpeed
        }
      })
      
      // Draw connections
      const nodes = nodesRef.current
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x
          const dy = nodes[i].y - nodes[j].y
          const dist = Math.sqrt(dx*dx + dy*dy)
          
          if (dist < cfg.connectionDist) {
            // Closer = more opaque line
            const alpha = (1 - dist / cfg.connectionDist) 
                          * cfg.lineOpacity
            
            // Pulse the line opacity
            const pulse = Math.sin(
              time + nodes[i].pulseOffset
            ) * 0.5 + 0.5
            
            ctx.beginPath()
            ctx.moveTo(nodes[i].x, nodes[i].y)
            ctx.lineTo(nodes[j].x, nodes[j].y)
            ctx.strokeStyle = cfg.lineColor
            ctx.globalAlpha = alpha * (0.5 + pulse * 0.5)
            ctx.lineWidth = 0.5
            ctx.stroke()
          }
        }
      }
      
      // Draw nodes
      nodes.forEach(node => {
        const pulse = Math.sin(time + node.pulseOffset)
        const size = node.isHub 
          ? (node.radius * 2.5) + pulse * 1.5
          : node.radius + pulse * 0.8
        
        // Speaking: ripple from center
        let rippleBoost = 1
        if (stateRef.current === 'speaking') {
          const distFromCenter = Math.sqrt(
            Math.pow(node.x - CX, 2) + 
            Math.pow(node.y - CY, 2)
          )
          rippleBoost = 1 + Math.sin(
            time * 3 - distFromCenter * 0.05
          ) * 0.5
        }
        
        // Outer glow
        ctx.globalAlpha = cfg.nodeOpacity * 0.3 * rippleBoost
        ctx.beginPath()
        ctx.arc(node.x, node.y, size * 3, 0, Math.PI * 2)
        ctx.fillStyle = cfg.nodeColor
        ctx.fill()
        
        // Inner glow
        ctx.globalAlpha = cfg.nodeOpacity * 0.6 * rippleBoost
        ctx.beginPath()
        ctx.arc(node.x, node.y, size * 1.5, 0, Math.PI * 2)
        ctx.fillStyle = cfg.nodeColor
        ctx.fill()
        
        // Core dot
        ctx.globalAlpha = cfg.nodeOpacity * rippleBoost
        ctx.beginPath()
        ctx.arc(node.x, node.y, size, 0, Math.PI * 2)
        ctx.fillStyle = cfg.nodeColor
        ctx.fill()
      })
      
      // Center hub — brightest node, always present
      const centerPulse = Math.sin(time * 1.5) * 0.5 + 0.5
      const centerSize = 4 + centerPulse * 3
      
      // Center glow rings
      ctx.globalAlpha = cfg.nodeOpacity * 0.15
      ctx.beginPath()
      ctx.arc(CX, CY, centerSize * 4, 0, Math.PI * 2)
      ctx.fillStyle = cfg.nodeColor
      ctx.fill()
      
      ctx.globalAlpha = cfg.nodeOpacity * 0.4
      ctx.beginPath()
      ctx.arc(CX, CY, centerSize * 2, 0, Math.PI * 2)
      ctx.fillStyle = cfg.nodeColor
      ctx.fill()
      
      ctx.globalAlpha = 1
      ctx.beginPath()
      ctx.arc(CX, CY, centerSize, 0, Math.PI * 2)
      ctx.fillStyle = cfg.nodeColor
      ctx.fill()
      
      ctx.globalAlpha = 1
      animRef.current = requestAnimationFrame(draw)
    }
    
    draw()
    
    return () => {
      if (animRef.current) {
        cancelAnimationFrame(animRef.current)
      }
    }
  }, []) // Only run once — state changes via stateRef
  
  const statusText = {
    idle: 'IDLE',
    listening: 'LISTENING . . .',
    thinking: 'PROCESSING',
    speaking: 'SPEAKING'
  }
  
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '1rem'
    }}>
      <canvas
        ref={canvasRef}
        width={400}
        height={400}
        style={{
          width: '280px',
          height: '280px'
        }}
      />
      <div style={{
        fontSize: '11px',
        letterSpacing: '0.3em',
        color: state === 'idle' ? '#0d2e2e' : '#00D9FF',
        fontWeight: 400,
        textTransform: 'uppercase',
        transition: 'color 0.5s ease'
      }}>
        {statusText[state] || 'IDLE'}
      </div>
    </div>
  )
}
