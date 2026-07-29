import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fileSystemMocks = vi.hoisted(() => ({
  uploadAsync: vi.fn(),
  cancelAsync: vi.fn(),
  createUploadTask: vi.fn(),
}));

vi.mock("react-native", () => ({
  Platform: { OS: "ios" },
}));

vi.mock("expo-constants", () => ({
  default: {
    expoConfig: { version: "1.0.0", ios: { buildNumber: "1" } },
    nativeBuildVersion: "1",
  },
}));

vi.mock("expo-file-system", () => ({
  FileSystemUploadType: { BINARY_CONTENT: 0 },
  FileSystemSessionType: { FOREGROUND: 1 },
  createUploadTask: fileSystemMocks.createUploadTask,
}));

import { resetAuthHooks, setAuthTokenProvider } from "../../api/auth";
import {
  completeSessionClipUpload,
  initiateSessionClipUpload,
  uploadClipToSession,
} from "../../api/clipApi";

describe("clipApi", () => {
  const originalUrl = process.env.EXPO_PUBLIC_API_URL;
  const fetchMock = vi.fn();

  beforeEach(() => {
    process.env.EXPO_PUBLIC_API_URL = "https://api.example.com";
    global.fetch = fetchMock;
    resetAuthHooks();
    setAuthTokenProvider(async () => "test-token");

    fileSystemMocks.uploadAsync.mockReset();
    fileSystemMocks.uploadAsync.mockResolvedValue({ status: 200, headers: {}, body: "" });
    fileSystemMocks.cancelAsync.mockReset();
    fileSystemMocks.cancelAsync.mockResolvedValue(undefined);
    fileSystemMocks.createUploadTask.mockReset();
    fileSystemMocks.createUploadTask.mockImplementation(
      (
        _url: string,
        _fileUri: string,
        _options: unknown,
        callback?: (data: { totalBytesSent: number; totalBytesExpectedToSend: number }) => void,
      ) => {
        callback?.({ totalBytesSent: 5, totalBytesExpectedToSend: 10 });
        return {
          uploadAsync: fileSystemMocks.uploadAsync,
          cancelAsync: fileSystemMocks.cancelAsync,
        };
      },
    );
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

  it("POSTs initiate-upload with required upload metadata", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          clip_id: "clip-1",
          upload_url: "https://s3.example.com/put",
          upload_method: "PUT",
          storage_key: "key-1",
          upload_expires_at: "2099-07-11T12:00:00Z",
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
    expect(res.data.upload_method).toBe("PUT");
  });

  it("rejects initiate responses that omit upload method or expiry", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ clip_id: "clip-1", upload_url: "https://s3", storage_key: "key" }), {
        status: 200,
      }),
    );
    const res = await initiateSessionClipUpload({
      sessionId: "sess-1",
      durationSeconds: 4,
      widthPx: 1920,
      heightPx: 1080,
      contentType: "video/mp4",
      sizeBytes: 12345,
    });
    expect(res.ok).toBe(false);
  });

  it("persists recovery before native upload and completes the job", async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            clip_id: "clip-9",
            upload_url: "https://s3.example.com/put",
            upload_method: "PUT",
            upload_expires_at: "2099-07-11T12:00:00Z",
            storage_key: "key-9",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response("{}", { status: 200 }));

    const lifecycle: string[] = [];
    fileSystemMocks.uploadAsync.mockImplementationOnce(async () => {
      lifecycle.push("upload");
      return { status: 200, headers: {}, body: "" };
    });
    const progress = vi.fn();
    const onInitiated = vi.fn(async () => {
      lifecycle.push("initiated");
    });
    const res = await uploadClipToSession({
      sessionId: "sess-1",
      fileUri: "file:///clip.mp4",
      mimeType: "video/mp4",
      durationSeconds: 5,
      widthPx: 1280,
      heightPx: 720,
      sizeBytes: 5000,
      onInitiated,
      onProgress: progress,
    });

    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.data).toBe("clip-9");
    expect(onInitiated).toHaveBeenCalledOnce();
    expect(lifecycle).toEqual(["initiated", "upload"]);
    expect(fileSystemMocks.uploadAsync).toHaveBeenCalledOnce();
    expect(progress).toHaveBeenCalledWith(0.5);
    expect(progress).toHaveBeenLastCalledWith(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][0]).toContain("/complete-upload");
  });

  it("does not upload bytes when recovery persistence fails", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          clip_id: "clip-10",
          upload_url: "https://s3.example.com/put",
          upload_method: "PUT",
          upload_expires_at: "2099-07-11T12:00:00Z",
          storage_key: "key-10",
        }),
        { status: 200 },
      ),
    );

    const res = await uploadClipToSession({
      sessionId: "sess-1",
      fileUri: "file:///clip.mp4",
      mimeType: "video/mp4",
      durationSeconds: 5,
      widthPx: 1280,
      heightPx: 720,
      sizeBytes: 5000,
      onInitiated: async () => {
        throw new Error("recovery write failed");
      },
    });

    expect(res.ok).toBe(false);
    if (!res.ok) {
      expect(res.error.kind).toBe("client");
      expect(res.error.message).toContain("recovery write failed");
    }
    expect(fileSystemMocks.createUploadTask).not.toHaveBeenCalled();
    expect(fileSystemMocks.uploadAsync).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("rejects oversized or overlong clips before network work", async () => {
    const res = await uploadClipToSession({
      sessionId: "sess-1",
      fileUri: "file:///clip.mp4",
      mimeType: "video/mp4",
      durationSeconds: 16,
      widthPx: 1280,
      heightPx: 720,
      sizeBytes: 5000,
    });
    expect(res.ok).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("treats complete-upload 409 as success", async () => {
    fetchMock.mockResolvedValueOnce(new Response("{}", { status: 409 }));
    const res = await completeSessionClipUpload("clip-1");
    expect(res.ok).toBe(true);
  });
});
