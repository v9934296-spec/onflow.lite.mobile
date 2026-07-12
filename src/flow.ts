export type ProtectedFlowRoute = "capture" | "analyzing" | "result";

export interface FlowSnapshot {
  trick: string | null;
  analysis: { trickCalled: string } | null;
  pendingClipJobId?: string | null;
}

export type FlowRedirect = "/trick" | "/capture" | null;

/**
 * Keeps deep links, back gestures, and stale in-memory state from entering a
 * flow screen without the state that screen requires.
 */
export function getFlowRedirect(
  route: ProtectedFlowRoute,
  snapshot: FlowSnapshot,
): FlowRedirect {
  if (!snapshot.trick) return "/trick";
  if (route === "capture") return null;

  if (route === "analyzing" && snapshot.pendingClipJobId) return null;

  if (!snapshot.analysis) return "/capture";
  if (snapshot.analysis.trickCalled !== snapshot.trick) return "/capture";

  return null;
}
