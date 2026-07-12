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

import { parseAccountMe } from "../../api/authApi";

describe("parseAccountMe", () => {
  it("parses a valid account response", () => {
    expect(
      parseAccountMe({
        user_id: "u1",
        email: "skater@example.com",
        tier: "free",
        profile_image_url: null,
        consent: { granted: true, granted_at: "2026-01-01", copy_version: "v1", source: "app" },
      }),
    ).toEqual({
      user_id: "u1",
      email: "skater@example.com",
      tier: "free",
      profile_image_url: null,
      consent: {
        granted: true,
        granted_at: "2026-01-01",
        copy_version: "v1",
        source: "app",
      },
    });
  });

  it("defaults tier to free and consent when absent", () => {
    const parsed = parseAccountMe({ user_id: "u1", email: "a@b.com" });
    expect(parsed?.tier).toBe("free");
    expect(parsed?.consent.granted).toBe(false);
  });

  it("rejects missing user_id", () => {
    expect(parseAccountMe({ email: "a@b.com" })).toBeNull();
    expect(parseAccountMe(null)).toBeNull();
  });

  it("accepts account without email when user_id is present", () => {
    const parsed = parseAccountMe({ user_id: "u1" });
    expect(parsed).toEqual({
      user_id: "u1",
      email: "",
      tier: "free",
      profile_image_url: null,
      consent: {
        granted: false,
        granted_at: null,
        copy_version: null,
        source: null,
      },
    });
  });
});
