export type TrickModifier = "fakie" | "nollie" | "switch" | "frontside" | "backside";

export interface SelectedTrick {
  /** Stable lowercase id for API (e.g. "kickflip", "fakie frontside kickflip"). */
  trickId: string;
  /** Base library trick name (e.g. "Kickflip"). */
  baseTrick: string;
  modifiers: TrickModifier[];
  /** Full display string (e.g. "Fakie frontside kickflip"). */
  canonicalName: string;
}

export function buildSelectedTrick(baseTrick: string, modifiers: TrickModifier[], canonicalName: string): SelectedTrick {
  return {
    trickId: canonicalName.trim().toLowerCase(),
    baseTrick,
    modifiers: [...modifiers],
    canonicalName,
  };
}
