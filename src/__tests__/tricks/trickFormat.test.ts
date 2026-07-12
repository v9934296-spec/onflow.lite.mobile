import { describe, expect, it } from "vitest";
import { canonicalTrickName, isLibraryTrickName, trickNameToId } from "../../tricks/trickFormat";

describe("canonicalTrickName", () => {
  it("returns library names unchanged when no modifiers", () => {
    expect(canonicalTrickName("Kickflip", [])).toBe("Kickflip");
    expect(canonicalTrickName("50-50", [])).toBe("50-50");
  });

  it("title-cases unknown base tricks without modifiers", () => {
    expect(canonicalTrickName("custom grind", [])).toBe("Custom Grind");
  });

  it("builds stance and direction prefixed canonical names", () => {
    expect(canonicalTrickName("Kickflip", ["fakie", "frontside"])).toBe("Fakie frontside kickflip");
    expect(canonicalTrickName("Tre flip", ["switch"])).toBe("Switch tre flip");
  });
});

describe("trickNameToId", () => {
  it("lowercases the canonical name for stable API ids", () => {
    expect(trickNameToId("Kickflip")).toBe("kickflip");
    expect(trickNameToId("Fakie frontside kickflip")).toBe("fakie frontside kickflip");
  });
});

describe("isLibraryTrickName", () => {
  it("recognizes catalog tricks and rejects unknown names", () => {
    expect(isLibraryTrickName("Kickflip")).toBe(true);
    expect(isLibraryTrickName("  Kickflip ")).toBe(true);
    expect(isLibraryTrickName("Not A Real Trick")).toBe(false);
  });
});
