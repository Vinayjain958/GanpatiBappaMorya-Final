/**
 * Pure linear-interpolation downsample + Float32 -> Int16 PCM conversion.
 * Mirrors the logic inlined in public/worklets/pcm-capture-worklet.js
 * (which can't import a module — AudioWorkletGlobalScope has no bundler
 * access) so the math itself stays unit-testable here.
 */
export function resampleAndEncodePCM16(
  input: Float32Array,
  sourceSampleRate: number,
  targetSampleRate: number,
): Int16Array {
  const ratio = sourceSampleRate / targetSampleRate;
  const outputLength = Math.floor(input.length / ratio);
  const output = new Int16Array(outputLength);

  for (let i = 0; i < outputLength; i++) {
    const sourceIndex = i * ratio;
    const lowerIndex = Math.floor(sourceIndex);
    const upperIndex = Math.min(lowerIndex + 1, input.length - 1);
    const fraction = sourceIndex - lowerIndex;
    const sample = input[lowerIndex] * (1 - fraction) + input[upperIndex] * fraction;
    const clamped = Math.max(-1, Math.min(1, sample));
    output[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  }

  return output;
}
