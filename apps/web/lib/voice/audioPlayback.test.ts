import { describe, expect, it } from "vitest";
import { base64ToInt16Array, int16ToFloat32 } from "@/lib/voice/audioPlayback";

function int16ToBase64(int16: Int16Array): string {
  const bytes = new Uint8Array(int16.buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

describe("base64ToInt16Array", () => {
  it("round-trips through base64 without data loss", () => {
    const original = new Int16Array([0, 1, -1, 32767, -32768, 12345, -12345]);
    const decoded = base64ToInt16Array(int16ToBase64(original));
    expect(Array.from(decoded)).toEqual(Array.from(original));
  });

  it("handles an empty buffer", () => {
    const decoded = base64ToInt16Array(int16ToBase64(new Int16Array([])));
    expect(decoded.length).toBe(0);
  });
});

describe("int16ToFloat32", () => {
  it("maps 0 to 0.0", () => {
    const float32 = int16ToFloat32(new Int16Array([0]));
    expect(float32[0]).toBe(0);
  });

  it("maps the positive max (32767) to approximately 1.0, never above", () => {
    const float32 = int16ToFloat32(new Int16Array([32767]));
    expect(float32[0]).toBeCloseTo(1.0, 4);
    expect(float32[0]).toBeLessThanOrEqual(1.0);
  });

  it("maps the negative max (-32768) to exactly -1.0", () => {
    const float32 = int16ToFloat32(new Int16Array([-32768]));
    expect(float32[0]).toBe(-1.0);
  });

  it("never produces a value outside [-1, 1]", () => {
    const samples = new Int16Array([0, 1, -1, 32767, -32768, 16000, -16000]);
    const float32 = int16ToFloat32(samples);
    for (const value of float32) {
      expect(value).toBeGreaterThanOrEqual(-1);
      expect(value).toBeLessThanOrEqual(1);
    }
  });

  it("preserves array length", () => {
    const samples = new Int16Array(10).fill(100);
    expect(int16ToFloat32(samples).length).toBe(10);
  });
});
