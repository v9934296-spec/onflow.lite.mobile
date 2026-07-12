/**
 * OnFlow trick library — canonical trick names and categories.
 * Modifiers are applied separately in the picker UI.
 */

export interface TrickCategory {
  id: string;
  label: string;
  tricks: string[];
}

export const TRICK_LIBRARY: TrickCategory[] = [
  {
    id: "fundamentals",
    label: "Fundamentals",
    tricks: [
      "Ollie",
      "Shuvit",
      "Pop shuvit",
      "Front shuvit",
      "360 shuvit",
      "Boneless",
      "No comply",
      "Powerslide",
      "Manual",
      "Nose manual",
    ],
  },
  {
    id: "flip",
    label: "Flip tricks",
    tricks: [
      "Kickflip",
      "Heelflip",
      "Pressureflip",
      "Varial kickflip",
      "Varial heelflip",
      "Hardflip",
      "Inward heelflip",
      "Tre flip",
      "Laser flip",
      "360 hardflip",
      "Double kickflip",
      "Double heelflip",
      "Impossible",
      "Dolphin flip",
      "Gazelle flip",
      "Bigflip",
      "Big heelflip",
      "Hospital flip",
      "Late flip",
    ],
  },
  {
    id: "grind",
    label: "Grinds",
    tricks: [
      "50-50",
      "5-0",
      "Nosegrind",
      "Crooked grind",
      "Smith grind",
      "Feeble grind",
      "Overcrook",
      "Willy grind",
      "Salad grind",
      "Hurricane",
    ],
  },
  {
    id: "slide",
    label: "Slides",
    tricks: [
      "Boardslide",
      "Lipslide",
      "Noseslide",
      "Tailslide",
      "Bluntslide",
      "Nosebluntslide",
      "Darkslide",
    ],
  },
  {
    id: "rotation",
    label: "Body / rotation",
    tricks: [
      "180",
      "360",
      "Bigspin",
      "Sex change",
      "Heelflip body varial",
      "Ghetto bird",
    ],
  },
  {
    id: "manual",
    label: "Manuals",
    tricks: [
      "Manual",
      "Nose manual",
      "One-footed manual",
      "Manual kickflip out",
      "Manual shuvit out",
    ],
  },
  {
    id: "transition",
    label: "Transition",
    tricks: [
      "Rock to fakie",
      "Rock and roll",
      "Axle stall",
      "Disaster",
      "Blunt to fakie",
    ],
  },
];

export const ALL_TRICKS: string[] = TRICK_LIBRARY.flatMap((cat) => cat.tricks);

export const POPULAR_TRICKS: readonly string[] = [
  "Ollie",
  "Kickflip",
  "Heelflip",
  "Pop shuvit",
  "Tre flip",
  "50-50",
  "Boardslide",
  "Manual",
];

export type TrickModifier = "fakie" | "nollie" | "switch" | "frontside" | "backside";

export const STANCE_MODIFIERS: TrickModifier[] = ["fakie", "nollie", "switch"];
export const DIRECTION_MODIFIERS: TrickModifier[] = ["frontside", "backside"];
