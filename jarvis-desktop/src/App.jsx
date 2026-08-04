import React, { useState, useEffect, useRef } from 'react'
import TitleBar from './components/TitleBar'
import Orb from './components/Orb'
import ChatLog from './components/ChatLog'
import InputBar from './components/InputBar'
import SystemVitals from './components/SystemVitals'
import DirectivesPanel from './components/DirectivesPanel'

export default function App() {
  const [orbState, setOrbState] = useState('idle')
  const [isConnected, setIsConnected] = useState(true)

  const activeUtteranceRef = useRef(null)
  const speechKeepAliveRef = useRef(null)
  const timeoutRef = useRef(null)

  const getInitialGreeting = () => {
    const hour = new Date().getHours()
    const timeGreeting = hour >= 5 && hour < 12 ? 'Good morning' : hour >= 12 && hour < 17 ? 'Good afternoon' : 'Good evening'
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
    return {
      role: 'jarvis',
      text: `${timeGreeting}, sir. JARVIS online and standing by.`,
      timestamp: timeStr
    }
  }

  const [messages, setMessages] = useState([getInitialGreeting()])

  const clearPendingTimeout = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
  }

  const stopSpeech = () => {
    if (speechKeepAliveRef.current) {
      clearInterval(speechKeepAliveRef.current)
      speechKeepAliveRef.current = null
    }
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel()
    }
    activeUtteranceRef.current = null
    setOrbState('idle')
  }

  const cleanTextForSpeech = (rawText) => {
    if (!rawText) return ''
    return rawText
      .replace(/```[\s\S]*?```/g, '')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/https?:\/\/\S+/g, '')
      .replace(/[*_#~>]/g, '')
      .replace(/^[\s-*+•\d.]+/gm, '')
      .replace(/\s+/g, ' ')
      .trim()
  }

  const speakResponse = (text) => {
    if (!('speechSynthesis' in window)) return

    stopSpeech()

    const cleanText = cleanTextForSpeech(text)
    if (!cleanText) {
      setOrbState('idle')
      return
    }

    setTimeout(() => {
      try {
        const utterance = new SpeechSynthesisUtterance(cleanText)
        activeUtteranceRef.current = utterance

        const voices = window.speechSynthesis.getVoices()
        const preferredVoice = voices.find(v => 
          v.name.includes('Ryan') || 
          v.name.includes('Natural') || 
          v.name.includes('Google UK English Male') ||
          (v.lang.startsWith('en') && v.name.includes('Male'))
        ) || voices.find(v => v.lang.startsWith('en'))

        if (preferredVoice) {
          utterance.voice = preferredVoice
        }

        utterance.rate = 1.0
        utterance.pitch = 1.0

        utterance.onstart = () => {
          setOrbState('speaking')
        }

        utterance.onend = () => {
          stopSpeech()
        }

        utterance.onerror = (e) => {
          console.warn('SpeechSynthesis error:', e)
          stopSpeech()
        }

        speechKeepAliveRef.current = setInterval(() => {
          if ('speechSynthesis' in window && window.speechSynthesis.speaking) {
            if (window.speechSynthesis.paused) {
              window.speechSynthesis.resume()
            }
          }
        }, 3000)

        window.speechSynthesis.speak(utterance)
      } catch (err) {
        console.error('Speech error:', err)
        setOrbState('idle')
      }
    }, 50)
  }

  useEffect(() => {
    const handleVoicesChanged = () => {
      if ('speechSynthesis' in window) {
        window.speechSynthesis.getVoices()
      }
    }

    if ('speechSynthesis' in window) {
      window.speechSynthesis.onvoiceschanged = handleVoicesChanged
      handleVoicesChanged()
      setTimeout(() => {
        speakResponse(messages[0]?.text)
      }, 300)
    }

    if (window.jarvis?.onResponse) {
      window.jarvis.onResponse((data) => {
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })

        if (data.type === 'response' || data.type === 'command_response') {
          clearPendingTimeout()
          const respText = data.text || 'Command executed, sir.'
          setMessages(prev => [...prev, {
            role: 'jarvis',
            text: respText,
            timestamp: timeStr,
            toolCalls: data.tool_calls || []
          }])
          speakResponse(respText)
        }
        else if (data.type === 'proactive_alert') {
          const alertText = data.text || 'Notification received, sir.'
          setMessages(prev => [...prev, {
            role: 'jarvis',
            text: alertText,
            timestamp: timeStr,
            isAlert: true,
            alertType: data.alert_type || 'reminder'
          }])
          speakResponse(alertText)
        }
        else if (data.type === 'status') {
          if (data.status === 'thinking') {
            setOrbState('thinking')
          } else if (data.status === 'connected') {
            setIsConnected(true)
            const greetingMsg = data.message || 'JARVIS online and standing by.'
            setMessages(prev => {
              if (prev.length === 1 && prev[0].role === 'jarvis' && prev[0].text.includes('standing by')) {
                return [{ role: 'jarvis', text: greetingMsg, timestamp: timeStr }]
              }
              if (prev.some(m => m.text === greetingMsg)) return prev
              return [...prev, { role: 'jarvis', text: greetingMsg, timestamp: timeStr }]
            })
            speakResponse(greetingMsg)
          } else if (data.status === 'disconnected') {
            setIsConnected(false)
            setOrbState('idle')
          }
        }
      })
    }

    if (window.jarvis?.onStatus) {
      window.jarvis.onStatus((status) => {
        if (status === 'connected') setIsConnected(true)
        if (status === 'disconnected') setIsConnected(false)
      })
    }

    return () => {
      clearPendingTimeout()
      stopSpeech()
      if ('speechSynthesis' in window) {
        window.speechSynthesis.onvoiceschanged = null
      }
    }
  }, [])

  const handleSendMessage = (text) => {
    stopSpeech()
    clearPendingTimeout()

    const cleanInput = text.trim()
    if (!cleanInput) return

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
    
    if (cleanInput.toLowerCase() === '/mute' || cleanInput.toLowerCase() === '/stop') {
      stopSpeech()
      setMessages(prev => [...prev, {
        role: 'user',
        text: cleanInput,
        timestamp: timeStr
      }, {
        role: 'jarvis',
        text: 'Playback muted, sir.',
        timestamp: timeStr
      }])
      return
    }

    setMessages(prev => [...prev, {
      role: 'user',
      text: cleanInput,
      timestamp: timeStr
    }])
    setOrbState('thinking')

    timeoutRef.current = setTimeout(() => {
      setOrbState('idle')
      setMessages(prev => [...prev, {
        role: 'jarvis',
        text: 'Connection timeout, sir. Please check if JARVIS backend is running.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
      }])
    }, 30000)

    if (cleanInput.startsWith('/')) {
      if (window.jarvis?.sendSlashCommand) {
        window.jarvis.sendSlashCommand(cleanInput)
      }
    } else {
      if (window.jarvis?.sendMessage) {
        window.jarvis.sendMessage(cleanInput)
      }
    }
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      width: '100vw',
      background: '#08080b',
      overflow: 'hidden'
    }}>
      <TitleBar isConnected={isConnected} />
      
      <div style={{
        display: 'flex',
        flex: 1,
        height: 'calc(100vh - 88px)',
        overflow: 'hidden'
      }}>
        <SystemVitals isConnected={isConnected} />

        <div style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          overflow: 'hidden',
          borderLeft: '1px solid rgba(255, 255, 255, 0.07)',
          borderRight: '1px solid rgba(255, 255, 255, 0.07)',
          background: '#08080b'
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            padding: '12px 0 4px 0'
          }}>
            <Orb state={orbState} />
          </div>

          <ChatLog messages={messages} />
        </div>

        <DirectivesPanel isConnected={isConnected} />
      </div>

      <InputBar onSend={handleSendMessage} />
    </div>
  )
}
