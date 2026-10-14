import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useLiveSession, type Status } from './useLiveSession'

const STATUS_TEXT: Record<Status, string> = {
  idle: 'തയ്യാറാണ് · Ready',
  connecting: 'ബന്ധിപ്പിക്കുന്നു…',
  listening: 'കേൾക്കുന്നു… മലയാളത്തിൽ സംസാരിക്കൂ',
  speaking: 'Gemini സംസാരിക്കുന്നു…',
  error: 'പിശക്',
}

export default function App() {
  const { status, error, messages, start, stop, sendText, live } = useLiveSession()
  const [voices, setVoices] = useState<string[]>(['Kore'])
  const [voice, setVoice] = useState('Kore')
  const [model, setModel] = useState('')
  const [text, setText] = useState('')
  const transcript = useRef<HTMLElement>(null)

  useEffect(() => {
    fetch('/api/voices').then((r) => r.json()).then((d) => { setVoices(d.voices); setVoice(d.default) }).catch(() => {})
    fetch('/api/health').then((r) => r.json()).then((d) => setModel(d.model)).catch(() => {})
  }, [])

  useEffect(() => {
    document.body.dataset.state = status
    transcript.current?.scrollTo({ top: transcript.current.scrollHeight })
  }, [status, messages])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    sendText(text.trim())
    setText('')
  }

  return (
    <main>
      <header>
        <h1>മലയാളം Talkback</h1>
        <p className="sub">React · WebSocket API · <code>{model || 'Gemini Live'}</code></p>
      </header>

      <section className="controls">
        <label>
          ശബ്ദം · Voice
          <select value={voice} onChange={(e) => setVoice(e.target.value)} disabled={live}>
            {voices.map((v) => <option key={v}>{v}</option>)}
          </select>
        </label>
        <button
          id="talk"
          type="button"
          className={live ? 'live' : ''}
          disabled={status === 'connecting'}
          onClick={() => (live ? stop() : start(voice))}
        >
          <span className="dot" />
          <span className="label">{live ? 'നിർത്തുക · Stop' : 'സംസാരിക്കാൻ തുടങ്ങുക · Start'}</span>
        </button>
        <p id="status" role="status">{error ? `പിശക്: ${error}` : STATUS_TEXT[status]}</p>
      </section>

      <section id="transcript" ref={transcript} aria-live="polite">
        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            <span className="who">{m.role === 'user' ? 'നിങ്ങൾ' : 'Gemini'}</span>
            <p>{m.text}</p>
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
          disabled={status !== 'listening' && status !== 'speaking'}
        />
        <button type="submit">അയയ്ക്കുക</button>
      </form>
    </main>
  )
}
