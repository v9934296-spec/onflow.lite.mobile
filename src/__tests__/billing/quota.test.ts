import { describe, expect, it } from "vitest";
import { isProTier, isQuotaExceededMessage } from "../../billing/quota";

describe("isQuotaExceededMessage", () => {
  it("detects quota and rate limit errors", () => {
    expect(isQuotaExceededMessage("HTTP 429 exceeded")).toBe(true);
    expect(isQuotaExceededMessage("Monthly quota reached")).toBe(true);
    expect(isQuotaExceededMessage("upload failed")).toBe(false);
  });
});

describe("isProTier", () => {
  it("recognizes pro tiers", () => {
    expect(isProTier("pro")).toBe(true);
    expect(isProTier("flow_plus")).toBe(true);
    expect(isProTier("free")).toBe(false);
    expect(isProTier(null)).toBe(false);
  });
});
