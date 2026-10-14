export type HistoryTurn = { role: 'user' | 'model'; text: string }
export type TalkResponse = {
  transcript: string
  reply: string
  audio_wav_base64: string
  timings_ms: Record<string, number>
}

async function parse(res: Response): Promise<TalkResponse> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`)
  }
  return res.json()
}

export async function talk(audio: Blob, history: HistoryTurn[], voice: string) {
  const form = new FormData()
  form.append('audio', audio, 'speech.wav')
  form.append('history', JSON.stringify(history))
  form.append('voice', voice)
  return parse(await fetch('/api/talk', { method: 'POST', body: form }))
}

export async function chat(text: string, history: HistoryTurn[], voice: string) {
  return parse(
    await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, history, voice }),
    }),
  )
}
