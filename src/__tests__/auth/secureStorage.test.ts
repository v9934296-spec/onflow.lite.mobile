import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const asyncGet = vi.fn();
const asyncSet = vi.fn();
const asyncRemove = vi.fn();
const secureGet = vi.fn();
const secureSet = vi.fn();
const secureDelete = vi.fn();

vi.mock("@react-native-async-storage/async-storage", () => ({
  default: {
    getItem: asyncGet,
    setItem: asyncSet,
    removeItem: asyncRemove,
  },
}));

vi.mock("expo-secure-store", () => ({
  getItemAsync: secureGet,
  setItemAsync: secureSet,
  deleteItemAsync: secureDelete,
}));

describe("secureStorage production behavior", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("JEST_WORKER_ID", "");
    asyncGet.mockReset();
    asyncSet.mockReset();
    asyncRemove.mockReset();
    secureGet.mockReset();
    secureSet.mockReset();
    secureDelete.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("does not downgrade a failed secure write to AsyncStorage", async () => {
    secureSet.mockRejectedValueOnce(new Error("keychain unavailable"));
    const { SecureStorageError, setSecureItem } = await import("../../auth/secureStorage");

    await expect(setSecureItem("token", "secret")).rejects.toBeInstanceOf(SecureStorageError);
    expect(asyncSet).not.toHaveBeenCalled();
  });

  it("does not report a clean delete when SecureStore deletion fails", async () => {
    secureDelete.mockRejectedValueOnce(new Error("delete failed"));
    const { SecureStorageError, removeSecureItem } = await import("../../auth/secureStorage");

    await expect(removeSecureItem("token")).rejects.toBeInstanceOf(SecureStorageError);
    expect(asyncRemove).not.toHaveBeenCalled();
  });

  it("keeps the legacy value when secure migration verification fails", async () => {
    asyncGet.mockResolvedValueOnce("legacy-secret");
    secureGet.mockResolvedValueOnce(null).mockResolvedValueOnce("different-value");
    secureSet.mockResolvedValueOnce(undefined);
    const { SecureStorageError, migrateFromAsyncStorage } = await import("../../auth/secureStorage");

    await expect(migrateFromAsyncStorage(["token"])).rejects.toBeInstanceOf(SecureStorageError);
    expect(asyncRemove).not.toHaveBeenCalled();
  });
});
