import { describe, expect, it } from "vitest";
import { buildSelectedTrick } from "../../tricks/types";

describe("buildSelectedTrick", () => {
  it("stores canonical name and lowercase trick id", () => {
    const selected = buildSelectedTrick("Kickflip", ["fakie"], "Fakie kickflip");
    expect(selected).toEqual({
      trickId: "fakie kickflip",
      baseTrick: "Kickflip",
      modifiers: ["fakie"],
      canonicalName: "Fakie kickflip",
    });
  });

  it("copies modifiers so callers cannot mutate shared state", () => {
    const mods = ["switch"] as const;
    const selected = buildSelectedTrick("Heelflip", [...mods], "Switch heelflip");
    (mods as unknown as string[]).push("fakie");
    expect(selected.modifiers).toEqual(["switch"]);
  });
});
