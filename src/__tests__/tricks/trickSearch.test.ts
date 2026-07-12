import { describe, expect, it } from "vitest";
import { filterTrickLibraryByQuery } from "../../tricks/trickSearch";
import { ALL_TRICKS } from "../../tricks/trickLibrary";

describe("filterTrickLibraryByQuery", () => {
  it("returns the full library when query is empty", () => {
    const categories = filterTrickLibraryByQuery("");
    const names = categories.flatMap((c) => c.tricks);
    expect(names).toEqual(ALL_TRICKS);
  });

  it("filters tricks by substring match", () => {
    const categories = filterTrickLibraryByQuery("flip");
    const names = categories.flatMap((c) => c.tricks);
    expect(names).toContain("Kickflip");
    expect(names).toContain("Heelflip");
    expect(names).not.toContain("Ollie");
  });

  it("prioritizes exact and prefix matches", () => {
    const categories = filterTrickLibraryByQuery("kickflip");
    const names = categories.flatMap((c) => c.tricks);
    expect(names[0]).toBe("Kickflip");
  });

  it("returns no categories when nothing matches", () => {
    expect(filterTrickLibraryByQuery("zzzznotatrick")).toEqual([]);
  });
});
