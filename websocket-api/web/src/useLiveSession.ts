import { useCallback, useEffect, useRef, useState } from 'react'

export type Role = 'user' | 'gemini'
export type Message = { id: number; role: Role; text: string }
export type Status = 'idle' | 'connecting' | 'listening' | 'speaking' | 'error'

type ServerEvent =
  | { type: 'ready'; model: string; voice: string }
  | { type: 'user' | 'gemini'; text: string }
  | { type: 'interrupted' | 'turn_complete' }
  | { type: 'error'; error: string }

/** Streams mic audio to /ws (16 kHz PCM) and plays Gemini's 24 kHz PCM replies. */
export function useLiveSession() {
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState('')
  const [messages, setMessages] = useState<Message[]>([])

  const ws = useRef<WebSocket | null>(null)
  const ctx = useRef<AudioContext | null>(null)
  const mic = useRef<MediaStream | null>(null)
  const node = useRef<AudioWorkletNode | null>(null)
  const playing = useRef<AudioBufferSourceNode[]>([])
  const nextTime = useRef(0)
  const openBubble = useRef<Role | null>(null)
  const nextId = useRef(0)

  const append = useCallback((role: Role, text: string) => {
    setMessages((prev) => {
      const last = prev[prev.length - 1]
      if (openBubble.current === role && last?.role === role) {
        return [...prev.slice(0, -1), { ...last, text: last.text + text }]
      }
      openBubble.current = role
      return [...prev, { id: nextId.current++, role, text }]
    })
  }, [])

  const stopPlayback = useCallback(() => {
    playing.current.forEach((s) => {
      try { s.stop() } catch { /* already stopped */ }
    })
    playing.current = []
    nextTime.current = 0
  }, [])

  const play = useCallback((buf: ArrayBuffer) => {
    const ac = ctx.current
    if (!ac) return
    const pcm = new Int16Array(buf)
    const audio = ac.createBuffer(1, pcm.length, 24000)
    const ch = audio.getChannelData(0)
    for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 32768
    const src = ac.createBufferSource()
    src.buffer = audio
    src.connect(ac.destination)
    nextTime.current = Math.max(ac.currentTime, nextTime.current)
    src.start(nextTime.current)
    nextTime.current += audio.duration
    playing.current.push(src)
    src.onended = () => { playing.current = playing.current.filter((s) => s !== src) }
    setStatus('speaking')
  }, [])

  const stop = useCallback(() => {
    node.current?.disconnect()
    node.current = null
    mic.current?.getTracks().forEach((t) => t.stop())
    mic.current = null
    stopPlayback()
    ctx.current?.close().catch(() => {})
    ctx.current = null
    const sock = ws.current
    ws.current = null
    if (sock && sock.readyState <= WebSocket.OPEN) sock.close()
    openBubble.current = null
    setStatus((s) => (s === 'error' ? s : 'idle'))
  }, [stopPlayback])

  const start = useCallback(async (voice: string) => {
    setError('')
    setStatus('connecting')
    try {
      const ac = new AudioContext()
      ctx.current = ac
      await ac.audioWorklet.addModule('/mic-processor.js')
      mic.current = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
    } catch {
      setError('മൈക്ക് അനുമതി ആവശ്യമാണ് (microphone permission needed)')
      setStatus('error')
      stop()
      return
    }

    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const sock = new WebSocket(`${proto}://${location.host}/ws?voice=${encodeURIComponent(voice)}`)
    sock.binaryType = 'arraybuffer'
    ws.current = sock

    sock.onmessage = (ev) => {
      if (ev.data instanceof ArrayBuffer) return play(ev.data)
      const msg = JSON.parse(ev.data) as ServerEvent
      switch (msg.type) {
        case 'ready': {
          const ac = ctx.current!
          const worklet = new AudioWorkletNode(ac, 'mic-processor')
          worklet.port.onmessage = (e) => {
            if (sock.readyState === WebSocket.OPEN) sock.send(e.data)
          }
          ac.createMediaStreamSource(mic.current!).connect(worklet)
          node.current = worklet
          setStatus('listening')
          break
        }
        case 'user':
        case 'gemini':
          append(msg.type, msg.text)
          break
        case 'interrupted':
          stopPlayback()
          openBubble.current = null
          break
        case 'turn_complete':
          openBubble.current = null
          setStatus('listening')
          break
        case 'error':
          setError(msg.error)
          setStatus('error')
          break
      }
    }
    sock.onclose = () => { if (ws.current === sock) stop() }
  }, [append, play, stop, stopPlayback])

  const sendText = useCallback((text: string) => {
    if (ws.current?.readyState !== WebSocket.OPEN) return
    openBubble.current = null
    append('user', text)
    openBubble.current = null
    ws.current.send(JSON.stringify({ type: 'text', text }))
  }, [append])

  useEffect(() => stop, [stop])

  return { status, error, messages, start, stop, sendText, live: status !== 'idle' && status !== 'error' }
}
