import { describe, expect, it } from "vitest";
import { getFlowRedirect } from "../flowGuard";

describe("getFlowRedirect", () => {
  it("sends capture to trick selection when no trick is active", () => {
    expect(getFlowRedirect("capture", { trick: null, analysis: null })).toBe("/trick");
  });

  it("sends analyzing and result back to capture when analysis is missing", () => {
    const snapshot = { trick: "Kickflip", analysis: null };
    expect(getFlowRedirect("analyzing", snapshot)).toBe("/capture");
    expect(getFlowRedirect("result", snapshot)).toBe("/capture");
  });

  it("allows analyzing while a clip job is pending", () => {
    const snapshot = { trick: "Kickflip", analysis: null, pendingClipJobId: "job-1" };
    expect(getFlowRedirect("analyzing", snapshot)).toBeNull();
    expect(getFlowRedirect("result", snapshot)).toBe("/capture");
  });

  it("rejects stale analysis from a previously selected trick", () => {
    const snapshot = {
      trick: "Tre Flip",
      analysis: { trickCalled: "Kickflip" },
    };
    expect(getFlowRedirect("result", snapshot)).toBe("/capture");
  });

  it("allows a complete, internally consistent flow state", () => {
    const snapshot = {
      trick: "Kickflip",
      analysis: { trickCalled: "Kickflip" },
    };
    expect(getFlowRedirect("analyzing", snapshot)).toBeNull();
    expect(getFlowRedirect("result", snapshot)).toBeNull();
  });
});
