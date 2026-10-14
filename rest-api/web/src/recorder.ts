/** Records the mic as 16 kHz mono 16-bit PCM and returns it as a WAV Blob. */
export class WavRecorder {
  private ctx: AudioContext | null = null
  private stream: MediaStream | null = null
  private node: AudioWorkletNode | null = null
  private chunks: Int16Array[] = []

  async start(): Promise<void> {
    this.chunks = []
    this.ctx = new AudioContext()
    await this.ctx.audioWorklet.addModule('/mic-processor.js')
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    })
    this.node = new AudioWorkletNode(this.ctx, 'mic-processor')
    this.node.port.onmessage = (e) => this.chunks.push(new Int16Array(e.data))
    this.ctx.createMediaStreamSource(this.stream).connect(this.node)
  }

  async stop(): Promise<Blob> {
    this.node?.disconnect()
    this.stream?.getTracks().forEach((t) => t.stop())
    await this.ctx?.close().catch(() => {})
    this.node = null
    this.stream = null
    this.ctx = null
    return encodeWav(this.chunks, 16000)
  }
}

function encodeWav(chunks: Int16Array[], sampleRate: number): Blob {
  const samples = chunks.reduce((n, c) => n + c.length, 0)
  const view = new DataView(new ArrayBuffer(44 + samples * 2))
  const str = (off: number, s: string) => [...s].forEach((ch, i) => view.setUint8(off + i, ch.charCodeAt(0)))
  str(0, 'RIFF')
  view.setUint32(4, 36 + samples * 2, true)
  str(8, 'WAVE')
  str(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  str(36, 'data')
  view.setUint32(40, samples * 2, true)
  let off = 44
  for (const c of chunks) for (const s of c) { view.setInt16(off, s, true); off += 2 }
  return new Blob([view], { type: 'audio/wav' })
}
