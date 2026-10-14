import { useEffect, useRef, useState, type FormEvent } from 'react'
import { chat, talk, type HistoryTurn, type TalkResponse } from './api'
import { WavRecorder } from './recorder'

type Status = 'idle' | 'recording' | 'thinking' | 'speaking' | 'error'
type Message = { id: number; role: 'user' | 'gemini'; text: string; timings?: Record<string, number> }

const STATUS_TEXT: Record<Status, string> = {
  idle: 'തയ്യാറാണ് · Press record and speak Malayalam',
  recording: 'റെക്കോർഡ് ചെയ്യുന്നു… കഴിഞ്ഞാൽ അയയ്ക്കുക',
  thinking: 'ആലോചിക്കുന്നു…',
  speaking: 'Gemini സംസാരിക്കുന്നു…',
  error: 'പിശക്',
}

let nextId = 0

export default function App() {
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [voices, setVoices] = useState<string[]>(['Kore'])
  const [voice, setVoice] = useState('Kore')
  const [models, setModels] = useState('')
  const [text, setText] = useState('')
  const recorder = useRef(new WavRecorder())
  const player = useRef<HTMLAudioElement | null>(null)
  const transcript = useRef<HTMLElement>(null)

  useEffect(() => {
    fetch('/api/voices').then((r) => r.json()).then((d) => { setVoices(d.voices); setVoice(d.default) }).catch(() => {})
    fetch('/api/health').then((r) => r.json()).then((d) => setModels(`${d.text_model} + ${d.tts_model}`)).catch(() => {})
  }, [])

  useEffect(() => {
    document.body.dataset.state = status
    transcript.current?.scrollTo({ top: transcript.current.scrollHeight })
  }, [status, messages])

  const history = (): HistoryTurn[] =>
    messages.map((m) => ({ role: m.role === 'user' ? 'user' : 'model', text: m.text }))

  async function run(request: () => Promise<TalkResponse>, userText?: string) {
    setError('')
    setStatus('thinking')
    if (userText) setMessages((m) => [...m, { id: nextId++, role: 'user', text: userText }])
    try {
      const res = await request()
      setMessages((m) => [
        ...m,
        ...(userText ? [] : [{ id: nextId++, role: 'user' as const, text: res.transcript }]),
        { id: nextId++, role: 'gemini', text: res.reply, timings: res.timings_ms },
      ])
      player.current?.pause()
      const audio = new Audio(`data:audio/wav;base64,${res.audio_wav_base64}`)
      player.current = audio
      audio.onended = () => setStatus('idle')
      setStatus('speaking')
      await audio.play().catch(() => setStatus('idle'))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus('error')
    }
  }

  async function toggleRecord() {
    if (status === 'recording') {
      const wav = await recorder.current.stop()
      await run(() => talk(wav, history(), voice))
      return
    }
    player.current?.pause()
    try {
      await recorder.current.start()
      setError('')
      setStatus('recording')
    } catch {
      setError('മൈക്ക് അനുമതി ആവശ്യമാണ് (microphone permission needed)')
      setStatus('error')
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    const t = text.trim()
    if (!t || status === 'thinking' || status === 'recording') return
    setText('')
    const h = history()
    void run(() => chat(t, h, voice), t)
  }

  const busy = status === 'thinking'
  return (
    <main>
      <header>
        <h1>മലയാളം Talkback</h1>
        <p className="sub">React · REST API · <code>{models || 'Gemini'}</code></p>
      </header>

      <section className="controls">
        <label>
          ശബ്ദം · Voice
          <select value={voice} onChange={(e) => setVoice(e.target.value)}>
            {voices.map((v) => <option key={v}>{v}</option>)}
          </select>
        </label>
        <button id="talk" type="button" className={status === 'recording' ? 'live' : ''} disabled={busy} onClick={toggleRecord}>
          <span className="dot" />
          <span className="label">{status === 'recording' ? 'അയയ്ക്കുക · Send' : 'റെക്കോർഡ് · Record'}</span>
        </button>
        <p id="status" role="status">{error ? `പിശക്: ${error}` : STATUS_TEXT[status]}</p>
      </section>

      <section id="transcript" ref={transcript} aria-live="polite">
        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            <span className="who">{m.role === 'user' ? 'നിങ്ങൾ' : 'Gemini'}</span>
            <p>{m.text}</p>
            {m.timings && (
              <p className="timings">
                {Object.entries(m.timings).map(([k, v]) => `${k} ${(v / 1000).toFixed(1)}s`).join(' · ')}
              </p>
            )}
          </div>
        ))}
      </section>

      <form id="text-form" onSubmit={submit}>
        <input
          id="text-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="അല്ലെങ്കിൽ ഇവിടെ ടൈപ്പ് ചെയ്യൂ…"
          autoComplete="off"
          disabled={busy || status === 'recording'}
        />
        <button type="submit" disabled={busy}>അയയ്ക്കുക</button>
      </form>
    </main>
  )
}
