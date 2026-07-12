import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getApiBaseUrl } from "../../api/baseUrl";

vi.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

describe("getApiBaseUrl", () => {
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;
  const originalWebUrl = process.env.EXPO_PUBLIC_API_URL_WEB;

  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    if (originalUrl === undefined) {
      delete process.env.EXPO_PUBLIC_API_URL;
    } else {
      process.env.EXPO_PUBLIC_API_URL = originalUrl;
    }
    if (originalWebUrl === undefined) {
      delete process.env.EXPO_PUBLIC_API_URL_WEB;
    } else {
      process.env.EXPO_PUBLIC_API_URL_WEB = originalWebUrl;
    }
  });

  it("returns trimmed native URL without trailing slash", () => {
    process.env.EXPO_PUBLIC_API_URL = "https://api.example.com/";
    expect(getApiBaseUrl()).toBe("https://api.example.com");
  });

  it("returns empty string when not configured on native", () => {
    delete process.env.EXPO_PUBLIC_API_URL;
    expect(getApiBaseUrl()).toBe("");
  });
});

describe("getApiBaseUrl (web)", () => {
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;
  const originalWebUrl = process.env.EXPO_PUBLIC_API_URL_WEB;

  beforeEach(async () => {
    vi.resetModules();
    vi.doMock("react-native", () => ({
      Platform: { OS: "web" },
    }));
  });

  afterEach(() => {
    vi.doUnmock("react-native");
    if (originalUrl === undefined) {
      delete process.env.EXPO_PUBLIC_API_URL;
    } else {
      process.env.EXPO_PUBLIC_API_URL = originalUrl;
    }
    if (originalWebUrl === undefined) {
      delete process.env.EXPO_PUBLIC_API_URL_WEB;
    } else {
      process.env.EXPO_PUBLIC_API_URL_WEB = originalWebUrl;
    }
  });

  it("rewrites LAN host to 127.0.0.1 on web", async () => {
    process.env.EXPO_PUBLIC_API_URL = "http://192.168.1.10:8000";
    const { getApiBaseUrl: getWebBaseUrl } = await import("../../api/baseUrl");
    expect(getWebBaseUrl()).toBe("http://127.0.0.1:8000");
  });

  it("uses EXPO_PUBLIC_API_URL_WEB override on web", async () => {
    process.env.EXPO_PUBLIC_API_URL = "http://192.168.1.10:8000";
    process.env.EXPO_PUBLIC_API_URL_WEB = "http://192.168.1.50:8000";
    const { getApiBaseUrl: getWebBaseUrl } = await import("../../api/baseUrl");
    expect(getWebBaseUrl()).toBe("http://192.168.1.50:8000");
  });

  it("defaults to localhost when empty on web", async () => {
    delete process.env.EXPO_PUBLIC_API_URL;
    const { getApiBaseUrl: getWebBaseUrl } = await import("../../api/baseUrl");
    expect(getWebBaseUrl()).toBe("http://127.0.0.1:8000");
  });
});
