// Captures mic audio, downsamples to 16 kHz and posts 16-bit PCM chunks (~100 ms).
class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.chunk = new Int16Array(1600);
    this.idx = 0;
    this.pos = 0;
  }

  process(inputs) {
    const input = inputs[0] && inputs[0][0];
    if (!input) return true;
    // Simple averaging decimator from the context rate to 16 kHz.
    while (this.pos < input.length) {
      const end = Math.min(input.length, this.pos + this.ratio);
      let sum = 0, n = 0;
      for (let i = Math.floor(this.pos); i < end; i++) { sum += input[i]; n++; }
      const s = Math.max(-1, Math.min(1, n ? sum / n : 0));
      this.chunk[this.idx++] = s < 0 ? s * 0x8000 : s * 0x7fff;
      if (this.idx === this.chunk.length) {
        this.port.postMessage(this.chunk.buffer.slice(0));
        this.idx = 0;
      }
      this.pos += this.ratio;
    }
    this.pos -= input.length;
    return true;
  }
}

registerProcessor("mic-processor", MicProcessor);
