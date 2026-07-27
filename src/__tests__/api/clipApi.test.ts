import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.stubGlobal("__DEV__", false);

vi.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

vi.mock("expo-constants", () => ({
  default: {
    expoConfig: { version: "1.0.0", ios: { buildNumber: "1" } },
    nativeBuildVersion: "1",
  },
}));

const uploadAsync = vi.fn();
vi.mock("expo-file-system", () => ({
  uploadAsync: (...args: unknown[]) => uploadAsync(...args),
  FileSystemUploadType: { BINARY_CONTENT: 0, MULTIPART: 1 },
}));

import {
  completeSessionClipUpload,
  initiateSessionClipUpload,
  uploadClipToSession,
} from "../../api/clipApi";
import { resetAuthHooks, setAuthTokenProvider } from "../../api/auth";

describe("clipApi", () => {
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;
  const fetchMock = vi.fn();

  beforeEach(() => {
    process.env.EXPO_PUBLIC_API_URL = "https://api.example.com";
    global.fetch = fetchMock;
    resetAuthHooks();
    setAuthTokenProvider(async () => "test-token");
    uploadAsync.mockReset();
    uploadAsync.mockResolvedValue({ status: 200 });
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

  it("POSTs initiate-upload with session and clip metadata", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          clip_id: "clip-1",
          upload_url: "https://s3.example.com/put",
          storage_key: "key-1",
          upload_expires_at: "2026-07-11T12:00:00Z",
        }),
        { status: 200 },
      ),
    );

    const res = await initiateSessionClipUpload({
      sessionId: "sess-1",
      durationSeconds: 4,
      widthPx: 1920,
      heightPx: 1080,
      contentType: "video/mp4",
      sizeBytes: 12345,
      clientHintTrickId: "kickflip",
    });

    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.data.clip_id).toBe("clip-1");
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/clips/initiate-upload");
  });

  it("uploadClipToSession runs initiate, native PUT, and complete-upload", async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            clip_id: "clip-9",
            upload_url: "https://s3.example.com/put",
            storage_key: "key-9",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response("{}", { status: 200 }));

    const res = await uploadClipToSession({
      sessionId: "sess-1",
      fileUri: "file:///clip.mp4",
      mimeType: "video/mp4",
      durationSeconds: 5,
      widthPx: 1280,
      heightPx: 720,
      sizeBytes: 5000,
    });

    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.data).toBe("clip-9");
    expect(uploadAsync).toHaveBeenCalledWith(
      "https://s3.example.com/put",
      "file:///clip.mp4",
      expect.objectContaining({
        httpMethod: "PUT",
        headers: { "Content-Type": "video/mp4" },
      }),
    );
    expect(fetchMock.mock.calls[1][0]).toContain("/complete-upload");
  });

  it("treats complete-upload 409 as success", async () => {
    fetchMock.mockResolvedValueOnce(new Response("{}", { status: 409 }));
    const res = await completeSessionClipUpload("clip-1");
    expect(res.ok).toBe(true);
  });
});
