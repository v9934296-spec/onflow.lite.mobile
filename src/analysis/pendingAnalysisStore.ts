import AsyncStorage from "@react-native-async-storage/async-storage";

import { userScopedStorageKey } from "../storage/userScopedStorage";
import type { SelectedTrick } from "../tricks/types";
import type { LoadResult, StorageResult } from "../types";

export interface PendingAnalysisJob {
  jobId: string;
  sessionId: string;
  trickName: string;
  selectedTrick: SelectedTrick | null;
  submittedAt: string;
}

function keyFor(userId: string): string {
  return userScopedStorageKey(userId, "pendingAnalysis");
}

function isSelectedTrick(value: unknown): value is SelectedTrick {
  if (!value || typeof value !== "object") return false;
  const o = value as Record<string, unknown>;
  return (
    typeof o.trickId === "string" &&
    typeof o.baseTrick === "string" &&
    Array.isArray(o.modifiers) &&
    o.modifiers.every((item) => typeof item === "string") &&
    typeof o.canonicalName === "string"
  );
}

function parsePendingAnalysisJob(value: unknown): PendingAnalysisJob | null {
  if (!value || typeof value !== "object") return null;
  const o = value as Record<string, unknown>;
  const jobId = typeof o.jobId === "string" ? o.jobId.trim() : "";
  const sessionId = typeof o.sessionId === "string" ? o.sessionId.trim() : "";
  const trickName = typeof o.trickName === "string" ? o.trickName.trim() : "";
  const submittedAt = typeof o.submittedAt === "string" ? o.submittedAt.trim() : "";
  const selectedTrick = o.selectedTrick == null ? null : isSelectedTrick(o.selectedTrick) ? o.selectedTrick : null;

  if (!jobId || !sessionId || !trickName || !submittedAt) return null;
  return { jobId, sessionId, trickName, selectedTrick, submittedAt };
}

export async function loadPendingAnalysisJob(
  userId: string,
): Promise<LoadResult<PendingAnalysisJob | null>> {
  try {
    const raw = await AsyncStorage.getItem(keyFor(userId));
    if (!raw) return { data: null };
    const parsed = parsePendingAnalysisJob(JSON.parse(raw) as unknown);
    if (!parsed) {
      return { data: null, loadError: "Saved analysis job has an invalid format" };
    }
    return { data: parsed };
  } catch (error) {
    return {
      data: null,
      loadError: error instanceof Error ? error.message : "Failed to load pending analysis",
    };
  }
}

export async function savePendingAnalysisJob(
  userId: string,
  job: PendingAnalysisJob,
): Promise<StorageResult> {
  try {
    await AsyncStorage.setItem(keyFor(userId), JSON.stringify(job));
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Failed to save pending analysis",
    };
  }
}

export async function clearPendingAnalysisJob(userId: string): Promise<StorageResult> {
  try {
    await AsyncStorage.removeItem(keyFor(userId));
    return { ok: true };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Failed to clear pending analysis",
    };
  }
}
