import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

vi.mock("expo-constants", () => ({
  default: {
    expoConfig: { version: "1.0.0", ios: { buildNumber: "1" } },
    nativeBuildVersion: "1",
  },
}));

import { fetchClipJob } from "../../api/jobApi";
import { pollClipJobUntilDone } from "../../analysis/pollClipJob";
import { resetAuthHooks, setAuthTokenProvider } from "../../api/auth";

describe("jobApi", () => {
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;
  const fetchMock = vi.fn();

  beforeEach(() => {
    process.env.EXPO_PUBLIC_API_URL = "https://api.example.com";
    global.fetch = fetchMock;
    resetAuthHooks();
    setAuthTokenProvider(async () => "test-token");
  });

  afterEach(() => {
    if (originalUrl === undefined) {
      delete process.env.EXPO_PUBLIC_API_URL;
    } else {
      process.env.EXPO_PUBLIC_API_URL = originalUrl;
    }
    fetchMock.mockReset();
    resetAuthHooks();
  });

  it("fetches and parses a clip job", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ job_id: "job-1", status: "processing" }), { status: 200 }),
    );
    const res = await fetchClipJob("job-1");
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.data.status).toBe("processing");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/clips/jobs/job-1");
  });
});

describe("pollClipJobUntilDone", () => {
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;
  const fetchMock = vi.fn();

  beforeEach(() => {
    process.env.EXPO_PUBLIC_API_URL = "https://api.example.com";
    global.fetch = fetchMock;
    resetAuthHooks();
    setAuthTokenProvider(async () => "test-token");
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    if (originalUrl === undefined) {
      delete process.env.EXPO_PUBLIC_API_URL;
    } else {
      process.env.EXPO_PUBLIC_API_URL = originalUrl;
    }
    fetchMock.mockReset();
    resetAuthHooks();
  });

  it("polls until a completed job is returned", async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ job_id: "job-1", status: "pending" }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            job_id: "job-1",
            status: "completed",
            result: {
              clip_label: "Ollie",
              review_summary: "Done",
              review_readiness: "usable",
              observations: [],
            },
          }),
          { status: 200 },
        ),
      );

    const promise = pollClipJobUntilDone("job-1", { intervalMs: 1000 });
    await vi.advanceTimersByTimeAsync(1000);
    const res = await promise;

    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.data.status).toBe("completed");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
