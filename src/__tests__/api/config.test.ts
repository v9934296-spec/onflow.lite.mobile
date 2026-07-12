import { afterEach, describe, expect, it } from "vitest";

import {
  getRawExpoApiUrl,
  guardApiBaseUrlAtStartup,
  isExpoApiUrlConfigured,
  missingApiBaseUserMessage,
} from "../../api/config";

describe("api config", () => {
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;

  afterEach(() => {
    if (originalUrl === undefined) {
      delete process.env.EXPO_PUBLIC_API_URL;
    } else {
      process.env.EXPO_PUBLIC_API_URL = originalUrl;
    }
  });

  it("detects missing EXPO_PUBLIC_API_URL", () => {
    delete process.env.EXPO_PUBLIC_API_URL;
    expect(isExpoApiUrlConfigured()).toBe(false);
    expect(getRawExpoApiUrl()).toBe("");
  });

  it("detects configured EXPO_PUBLIC_API_URL", () => {
    process.env.EXPO_PUBLIC_API_URL = "https://api.example.com";
    expect(isExpoApiUrlConfigured()).toBe(true);
    expect(getRawExpoApiUrl()).toBe("https://api.example.com");
  });

  it("trims whitespace from EXPO_PUBLIC_API_URL", () => {
    process.env.EXPO_PUBLIC_API_URL = "  https://api.example.com  ";
    expect(getRawExpoApiUrl()).toBe("https://api.example.com");
  });

  it("returns user-facing message when URL is missing", () => {
    delete process.env.EXPO_PUBLIC_API_URL;
    const message = missingApiBaseUserMessage();
    expect(message).toMatch(/server address|EXPO_PUBLIC_API_URL/);
  });

  it("skips startup guard under test", () => {
    delete process.env.EXPO_PUBLIC_API_URL;
    expect(() => guardApiBaseUrlAtStartup()).not.toThrow();
  });
});
