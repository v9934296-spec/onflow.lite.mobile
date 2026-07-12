import type { TrickCategory } from "./trickLibrary";
import { ALL_TRICKS, TRICK_LIBRARY } from "./trickLibrary";

function scoreTrickName(name: string, q: string): number {
  const n = name.toLowerCase();
  const query = q.toLowerCase();
  if (!query) return 1;
  if (n === query) return 100;
  if (n.startsWith(query)) return 80;
  if (n.includes(query)) return 60;
  const words = n.split(/\s+/);
  if (words.some((w) => w.startsWith(query))) return 50;
  return -1;
}

export function filterTrickLibraryByQuery(query: string): TrickCategory[] {
  const q = query.trim();
  if (!q) {
    return TRICK_LIBRARY.map((c) => ({ ...c, tricks: [...c.tricks] }));
  }

  const ranked = ALL_TRICKS.map((name) => ({ name, score: scoreTrickName(name, q) }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score || a.name.localeCompare(b.name));

  const matchSet = new Set(ranked.map((r) => r.name));

  return TRICK_LIBRARY.map((cat) => ({
    ...cat,
    tricks: cat.tricks.filter((t) => matchSet.has(t)),
  })).filter((cat) => cat.tricks.length > 0);
}
