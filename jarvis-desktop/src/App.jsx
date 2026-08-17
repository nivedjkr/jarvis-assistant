import React, { useState, useEffect, useRef } from 'react'
import TitleBar from './components/TitleBar'
import Orb from './components/Orb'
import ChatLog from './components/ChatLog'
import InputBar from './components/InputBar'
import SystemVitals from './components/SystemVitals'
import DirectivesPanel from './components/DirectivesPanel'
import EmailPanel from './components/EmailPanel'

export default function App() {
  const [orbState, setOrbState] = useState('idle')
  const [isConnected, setIsConnected] = useState(true)
  const [lastStateUpdate, setLastStateUpdate] = useState(null)

  const activeAudioRef = useRef(null)
  const timeoutRef = useRef(null)
  const playbackSessionRef = useRef(0)
  const sentenceQueueRef = useRef([])
  const isSpeakingRef = useRef(false)
  const streamingTextRef = useRef('')
  const lastProcessedSentenceIndexRef = useRef(0)

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
    playbackSessionRef.current += 1

    if (activeAudioRef.current) {
      try {
        activeAudioRef.current.pause()
        activeAudioRef.current.currentTime = 0
      } catch (e) {
        console.warn('Error stopping audio:', e)
      }
      activeAudioRef.current = null
    }

    sentenceQueueRef.current = []
    isSpeakingRef.current = false
    streamingTextRef.current = ''
    lastProcessedSentenceIndexRef.current = 0
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

  const processNextSentence = async () => {
    const currentSession = playbackSessionRef.current

    if (sentenceQueueRef.current.length === 0) {
      isSpeakingRef.current = false
      setOrbState('idle')
      return
    }

    isSpeakingRef.current = true
    const item = sentenceQueueRef.current.shift()
    if (!item || !item.promise) {
      processNextSentence()
      return
    }

    try {
      const audioData = await item.promise
      if (currentSession !== playbackSessionRef.current) return

      if (!audioData) {
        processNextSentence()
        return
      }

      const audio = new Audio(audioData)
      activeAudioRef.current = audio

      audio.onplay = () => {
        if (currentSession === playbackSessionRef.current) {
          setOrbState('speaking')
        }
      }

      audio.onended = () => {
        activeAudioRef.current = null
        if (currentSession === playbackSessionRef.current) {
          processNextSentence()
        }
      }

      audio.onerror = (e) => {
        console.warn('Audio playback error:', e)
        activeAudioRef.current = null
        if (currentSession === playbackSessionRef.current) {
          processNextSentence()
        }
      }

      setOrbState('speaking')
      audio.play().catch(err => {
        console.warn('Failed to play audio:', err)
        activeAudioRef.current = null
        if (currentSession === playbackSessionRef.current) {
          processNextSentence()
        }
      })
    } catch (err) {
      console.error('Sentence synthesis error:', err)
      if (currentSession === playbackSessionRef.current) {
        processNextSentence()
      }
    }
  }

  const enqueueSentences = (text) => {
    if (!text) return
    const sentences = text.split(/(?<=[.!?])\s+/).map(s => s.trim()).filter(Boolean)
    if (sentences.length === 0) return

    for (const sentence of sentences) {
      const clean = cleanTextForSpeech(sentence)
      if (clean) {
        const promise = window.jarvis?.synthesizeSentence
          ? window.jarvis.synthesizeSentence(clean)
          : Promise.resolve('')
        sentenceQueueRef.current.push({ text: clean, promise })
      }
    }

    if (!isSpeakingRef.current) {
      processNextSentence()
    }
  }

  const speakResponse = async (text, preloadedAudioUrl = null) => {
    stopSpeech()

    const cleanText = cleanTextForSpeech(text)
    if (!cleanText) {
      setOrbState('idle')
      return
    }

    if (preloadedAudioUrl) {
      const currentSession = playbackSessionRef.current
      try {
        const audio = new Audio(preloadedAudioUrl)
        activeAudioRef.current = audio

        audio.onplay = () => {
          if (currentSession === playbackSessionRef.current) {
            setOrbState('speaking')
          }
        }

        audio.onended = () => {
          activeAudioRef.current = null
          if (currentSession === playbackSessionRef.current) {
            stopSpeech()
          }
        }

        audio.onerror = (e) => {
          console.warn('Audio playback error:', e)
          activeAudioRef.current = null
          if (currentSession === playbackSessionRef.current) {
            enqueueSentences(cleanText)
          }
        }

        setOrbState('speaking')
        audio.play().catch(err => {
          console.warn('Failed to play audio:', err)
          activeAudioRef.current = null
          if (currentSession === playbackSessionRef.current) {
            enqueueSentences(cleanText)
          }
        })
        return
      } catch (err) {
        console.warn('Audio element error:', err)
      }
    }

    enqueueSentences(cleanText)
  }

  useEffect(() => {
    speakResponse(messages[0]?.text)

    if (window.jarvis?.onResponse) {
      window.jarvis.onResponse((data) => {
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })

        if (data.type === 'chunk') {
          clearPendingTimeout()
          const chunkText = data.text || ''
          setMessages(prev => {
            const last = prev[prev.length - 1]
            if (last && last.role === 'jarvis' && last.isStreaming) {
              return [
                ...prev.slice(0, -1),
                { ...last, text: last.text + chunkText }
              ]
            } else {
              return [
                ...prev,
                { role: 'jarvis', text: chunkText, timestamp: timeStr, isStreaming: true }
              ]
            }
          })

          streamingTextRef.current += chunkText
          const fullText = streamingTextRef.current
          const completedSentences = fullText.slice(lastProcessedSentenceIndexRef.current).match(/[^.!?]+[.!?]+(\s+|$)/g)
          
          if (completedSentences && completedSentences.length > 0) {
            for (const sentence of completedSentences) {
              if (/[.!?]/.test(sentence)) {
                lastProcessedSentenceIndexRef.current += sentence.length
                const clean = cleanTextForSpeech(sentence)
                if (clean) {
                  sentenceQueueRef.current.push(clean)
                  if (!isSpeakingRef.current) {
                    processNextSentence()
                  }
                }
              }
            }
          } else if (!isSpeakingRef.current) {
            setOrbState('thinking')
          }
        }
        else if (data.type === 'response' || data.type === 'command_response') {
          clearPendingTimeout()
          const respText = data.text || 'Command executed, sir.'
          setMessages(prev => {
            const filtered = prev.filter(m => !m.isStreaming)
            return [...filtered, {
              role: 'jarvis',
              text: respText,
              timestamp: timeStr,
              toolCalls: data.tool_calls || []
            }]
          })

          if (data.audio) {
            speakResponse(respText, data.audio)
          } else {
            const remainingText = streamingTextRef.current.slice(lastProcessedSentenceIndexRef.current)
            const cleanTail = cleanTextForSpeech(remainingText || respText)
            
            if (cleanTail && (!sentenceQueueRef.current.length && !isSpeakingRef.current)) {
              enqueueSentences(cleanTail)
            } else if (cleanTail && isSpeakingRef.current) {
              sentenceQueueRef.current.push(cleanTail)
            } else if (!sentenceQueueRef.current.length && !isSpeakingRef.current) {
              speakResponse(respText)
            }
          }

          streamingTextRef.current = ''
          lastProcessedSentenceIndexRef.current = 0
        }
        else if (data.type === 'proactive_alert') {
          clearPendingTimeout()
          const alertText = data.text || 'Notification received, sir.'
          setMessages(prev => [...prev, {
            role: 'jarvis',
            text: alertText,
            timestamp: timeStr,
            isAlert: true,
            alertType: data.alert_type || 'reminder'
          }])
          speakResponse(alertText, data.audio)
        }
        else if (data.type === 'state_update') {
          console.log('[UI] Real-time state update received:', data)
          setLastStateUpdate({
            domain: data.domain,
            action: data.action,
            payload: data.payload,
            timestamp: Date.now()
          })
        }
        else if (data.type === 'status') {
          if (data.status === 'thinking') {
            clearPendingTimeout()
            setOrbState('thinking')
            // Re-arm timer for 60s while backend is actively processing/thinking
            timeoutRef.current = setTimeout(() => {
              setOrbState('idle')
              setMessages(prev => [...prev, {
                role: 'jarvis',
                text: 'Connection timeout, sir. Please check if JARVIS backend is running.',
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
              }])
            }, 60000)
          } else if (data.status === 'connected') {
            clearPendingTimeout()
            setIsConnected(true)
            const greetingMsg = data.message || 'JARVIS online and standing by.'
            setMessages(prev => {
              if (prev.length === 1 && prev[0].role === 'jarvis' && prev[0].text.includes('standing by')) {
                return [{ role: 'jarvis', text: greetingMsg, timestamp: timeStr }]
              }
              if (prev.some(m => m.text === greetingMsg)) return prev
              return [...prev, { role: 'jarvis', text: greetingMsg, timestamp: timeStr }]
            })
            speakResponse(greetingMsg, data.audio)
          } else if (data.status === 'disconnected') {
            clearPendingTimeout()
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
    }, 60000)

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
      background: '#040406',
      color: '#e8e6e0',
      fontFamily: "'JetBrains Mono', monospace",
      overflow: 'hidden'
    }}>
      <TitleBar isConnected={isConnected} />
      
      <div style={{
        display: 'flex',
        flex: 1,
        height: 'calc(100vh - 88px)',
        overflow: 'hidden'
      }}>
        <SystemVitals isConnected={isConnected} lastStateUpdate={lastStateUpdate} />

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

        <DirectivesPanel isConnected={isConnected} lastStateUpdate={lastStateUpdate} />
        <EmailPanel isConnected={isConnected} lastStateUpdate={lastStateUpdate} />
      </div>

      <InputBar onSend={handleSendMessage} />
    </div>
  )
}
