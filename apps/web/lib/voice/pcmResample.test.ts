import { describe, expect, it } from "vitest";
import { resampleAndEncodePCM16 } from "@/lib/voice/pcmResample";

describe("resampleAndEncodePCM16", () => {
  it("downsamples 48kHz to 16kHz at approximately a 3:1 ratio", () => {
    const input = new Float32Array(48000); // 1 second of silence at 48kHz
    const output = resampleAndEncodePCM16(input, 48000, 16000);
    expect(output.length).toBeCloseTo(16000, -2); // within ~100 samples
  });

  it("passes through unchanged when source equals target rate", () => {
    const input = new Float32Array([0, 0.5, -0.5, 1, -1]);
    const output = resampleAndEncodePCM16(input, 16000, 16000);
    expect(output.length).toBe(input.length);
  });

  it("clamps Int16 output within range, never overflowing", () => {
    const input = new Float32Array(100).fill(1.5); // out-of-range input
    const output = resampleAndEncodePCM16(input, 16000, 16000);
    for (const sample of output) {
      expect(sample).toBeGreaterThanOrEqual(-32768);
      expect(sample).toBeLessThanOrEqual(32767);
    }
  });

  it("maps full-scale +1.0 and -1.0 to near Int16 extremes", () => {
    const input = new Float32Array([1, -1]);
    const output = resampleAndEncodePCM16(input, 16000, 16000);
    expect(output[0]).toBeCloseTo(32767, -1);
    expect(output[1]).toBe(-32768);
  });

  it("produces silence for silent input", () => {
    const input = new Float32Array(1000).fill(0);
    const output = resampleAndEncodePCM16(input, 48000, 16000);
    expect(output.every((sample) => sample === 0)).toBe(true);
  });
});
