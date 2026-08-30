// High-performance AudioWorkletProcessor with zero-GC dynamic sample rate resampling to 16kHz PCM16
class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    // 320 samples @ 16kHz = 20ms frame duration (640 bytes PCM16)
    this.frameSize = 320;
    this.buffer = new Int16Array(this.frameSize);
    this.bufIndex = 0;
    this.inputSampleRate = sampleRate; // Global AudioWorklet sampleRate (e.g. 48000 or 44100)
    this.ratio = this.inputSampleRate / this.targetSampleRate;
    this.phase = 0;
  }

  process(inputs) {
    const input = inputs[0][0];
    if (!input || input.length === 0) return true;

    // Resample input Float32Array to 16000 Hz with linear interpolation
    while (this.phase < input.length) {
      const idx = Math.floor(this.phase);
      const frac = this.phase - idx;
      const nextIdx = Math.min(idx + 1, input.length - 1);
      const sample = input[idx] * (1 - frac) + input[nextIdx] * frac;
      
      // Convert Float32 [-1.0, 1.0] to PCM16 [-32768, 32767]
      const clamped = Math.max(-1.0, Math.min(1.0, sample));
      this.buffer[this.bufIndex++] = clamped < 0 ? clamped * 32768 : clamped * 32767;

      // When 20ms frame is full, transfer immediately to main thread
      if (this.bufIndex >= this.frameSize) {
        this.port.postMessage(this.buffer.buffer.slice(0));
        this.bufIndex = 0;
      }

      this.phase += this.ratio;
    }
    this.phase -= input.length;

    return true;
  }
}

registerProcessor('mic-processor', MicProcessor);
