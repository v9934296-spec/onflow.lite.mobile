import { describe, expect, it, vi } from "vitest";

vi.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

import {
  configurationFailureMessage,
  extractApiErrorBody,
  formatApiDetail,
  isAbortError,
  isNetworkFetchError,
} from "../../api/errors";

describe("api errors", () => {
  it("formats string detail", () => {
    expect(formatApiDetail("Session not found")).toBe("Session not found");
  });

  it("formats validation array detail", () => {
    expect(formatApiDetail([{ msg: "field required" }])).toBe("field required");
  });

  it("extracts FastAPI detail from JSON body", () => {
    expect(extractApiErrorBody({ detail: "Not found" })).toBe("Not found");
  });

  it("returns null when detail is absent", () => {
    expect(extractApiErrorBody({ error: "x" })).toBeNull();
  });

  it("detects network fetch errors", () => {
    expect(isNetworkFetchError(new Error("Network request failed"))).toBe(true);
    expect(isNetworkFetchError(new Error("failed to fetch"))).toBe(true);
    expect(isNetworkFetchError(new Error("other"))).toBe(false);
  });

  it("detects abort errors", () => {
    const err = new Error("aborted");
    err.name = "AbortError";
    expect(isAbortError(err)).toBe(true);
  });

  it("returns configuration failure message", () => {
    expect(configurationFailureMessage()).toMatch(/EXPO_PUBLIC_API_URL|server address/);
  });
});
