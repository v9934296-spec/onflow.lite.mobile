import { describe, expect, it } from "vitest";
import {
  analyzeSample,
  analyzeUserClip,
  computeConfidence,
  deriveEvidenceClass,
  ENGINE_VERSION,
  MIN_CONFIDENCE_FOR_RATING,
  SAMPLE_CLIPS,
} from "../engine";

describe("analyzeUserClip", () => {
  it("never returns DETECTED on user footage", () => {
    const result = analyzeUserClip("file:///clip.mp4", 5, "Kickflip");
    expect(result.observations.every((o) => o.tag !== "DETECTED")).toBe(true);
    expect(result.evidenceClass).toBe("ESTIMATE");
  });

  it("never returns a numeric rating for valid user clips", () => {
    const result = analyzeUserClip("file:///clip.mp4", 5, "Kickflip");
    expect(result.rating).toBeNull();
    expect(result.breakdown).toBeNull();
    expect(result.selfReportOnly).toBe(true);
  });

  it("stamps engineVersion on every result", () => {
    const result = analyzeUserClip("file:///clip.mp4", 5, "Kickflip");
    expect(result.engineVersion).toBe(ENGINE_VERSION);
    expect(result.receipts.some((r) => r.id === "engine-version")).toBe(true);
  });

  it("abstains on clips under 2 seconds", () => {
    const result = analyzeUserClip("file:///short.mp4", 1.5, "Ollie");
    expect(result.abstained).toBe(true);
    expect(result.rating).toBeNull();
    expect(result.abstainReason).toBeTruthy();
  });

  it("abstains when duration is unknown", () => {
    const result = analyzeUserClip("file:///unknown.mp4", null, "Ollie");
    expect(result.abstained).toBe(true);
  });
});

describe("analyzeSample", () => {
  it("prepends mismatch callout when trick does not match sample", () => {
    const clip = SAMPLE_CLIPS.find((c) => c.id === "kf-flat")!;
    const result = analyzeSample(clip, "Tre Flip");
    expect(result.mismatch).toBe(true);
    expect(result.observations[0].text).toMatch(/called tre flip/i);
    expect(result.observations[0].tag).toBe("DETECTED");
  });

  it("returns scripted kickflip analysis when trick matches", () => {
    const clip = SAMPLE_CLIPS.find((c) => c.id === "kf-flat")!;
    const result = analyzeSample(clip, "Kickflip");
    expect(result.rating).toBe(6.5);
    expect(result.mismatch).toBe(false);
    expect(result.evidenceClass).toBe("DETECTED");
    expect(result.confidence).toBeGreaterThanOrEqual(MIN_CONFIDENCE_FOR_RATING);
  });

  it("abstains on 5-stair sample with incomplete landing", () => {
    const clip = SAMPLE_CLIPS.find((c) => c.id === "ollie-5")!;
    const result = analyzeSample(clip, "Ollie");
    expect(result.abstained).toBe(true);
    expect(result.rating).toBeNull();
    expect(result.abstainReason).toBeTruthy();
  });

  it("includes receipts traceable to observations", () => {
    const clip = SAMPLE_CLIPS.find((c) => c.id === "kf-flat")!;
    const result = analyzeSample(clip, "Kickflip");
    expect(result.receipts.length).toBeGreaterThan(0);
  });
});

describe("evidence helpers", () => {
  it("deriveEvidenceClass never returns DETECTED for user source without detected obs", () => {
    expect(
      deriveEvidenceClass([{ text: "x", tag: "ESTIMATE" }], "user"),
    ).toBe("ESTIMATE");
  });

  it("computeConfidence weights DETECTED higher than ESTIMATE", () => {
    const high = computeConfidence([
      { text: "a", tag: "DETECTED" },
      { text: "b", tag: "DETECTED" },
    ]);
    const low = computeConfidence([{ text: "a", tag: "ESTIMATE" }]);
    expect(high).toBeGreaterThan(low);
  });
});
