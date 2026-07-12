import {
  ALL_TRICKS,
  DIRECTION_MODIFIERS,
  STANCE_MODIFIERS,
  type TrickModifier,
} from "./trickLibrary";

const LIBRARY_SET = new Set(ALL_TRICKS);

export function isLibraryTrickName(name: string): boolean {
  return LIBRARY_SET.has(name.trim());
}

function capitalizeWord(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

function titleCaseWords(s: string): string {
  return s
    .trim()
    .replace(/\s+/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((w) => (/^\d/.test(w) ? w : capitalizeWord(w)))
    .join(" ");
}

export function canonicalTrickName(baseTrick: string, modifiers: TrickModifier[]): string {
  const raw = baseTrick.trim().replace(/\s+/g, " ");
  if (!raw) return "";

  if (modifiers.length === 0) {
    if (LIBRARY_SET.has(raw)) return raw;
    return titleCaseWords(raw.toLowerCase());
  }

  const stance = modifiers.find((m) => STANCE_MODIFIERS.includes(m));
  const direction = modifiers.find((m) => DIRECTION_MODIFIERS.includes(m));

  const parts: string[] = [];
  if (stance) parts.push(capitalizeWord(stance));
  if (direction) parts.push(direction);
  parts.push(raw.toLowerCase());

  return parts.join(" ");
}

export function trickNameToId(canonicalName: string): string {
  return canonicalName.trim().toLowerCase();
}
