import { describe, expect, it, vi } from "vitest";

vi.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

vi.mock("expo-constants", () => ({
  default: {
    expoConfig: { version: "1.0.0" },
    nativeBuildVersion: "1",
  },
}));

import { parseHealthResponse } from "../../api/health";

describe("parseHealthResponse", () => {
  it("accepts minimal response with status only", () => {
    expect(parseHealthResponse({ status: "ok" })).toEqual({ status: "ok" });
  });

  it("accepts full diagnostic fields when present", () => {
    expect(
      parseHealthResponse({
        status: "ok",
        db: "ok",
        gemini_configured: true,
        twelvelabs_configured: false,
        clip_review_ready: false,
      }),
    ).toEqual({
      status: "ok",
      db: "ok",
      gemini_configured: true,
      twelvelabs_configured: false,
      clip_review_ready: false,
    });
  });

  it("ignores unknown extra fields", () => {
    const parsed = parseHealthResponse({ status: "ok", future_field: "x" });
    expect(parsed).toEqual({ status: "ok" });
    expect(parsed).not.toHaveProperty("future_field");
  });

  it("rejects missing status", () => {
    expect(parseHealthResponse({ db: "ok" })).toBeNull();
  });

  it("rejects empty status", () => {
    expect(parseHealthResponse({ status: "  " })).toBeNull();
  });

  it("rejects non-object input", () => {
    expect(parseHealthResponse(null)).toBeNull();
    expect(parseHealthResponse("ok")).toBeNull();
  });
});
