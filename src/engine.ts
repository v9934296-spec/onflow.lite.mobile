import { Analysis, Observation, SampleClip } from "./types";

export const TRICKS = [
  "Ollie",
  "Kickflip",
  "Heelflip",
  "Pop Shove-it",
  "Tre Flip",
  "BS 50-50",
  "FS Boardslide",
  "Nollie",
] as const;

export const SAMPLE_CLIPS: SampleClip[] = [
  { id: "kf-flat", label: "Kickflip — flat", canonical: "Kickflip", spot: "Embarcadero flat", durationSec: 6 },
  { id: "bs-5050", label: "BS 50-50 — ledge", canonical: "BS 50-50", spot: "3rd & Army ledge", durationSec: 8 },
  { id: "ollie-5", label: "Ollie — 5 stair", canonical: "Ollie", spot: "Mission High 5", durationSec: 4 },
];

const SCRIPTED: Record<string, Omit<Analysis, "trickCalled" | "mismatch" | "source">> = {
  "kf-flat": {
    trickOnFilm: "Kickflip",
    abstained: false,
    rating: 6.5,
    verdict: "Clean catch, lazy back foot.",
    observations: [
      { text: "Full flip rotation caught with front foot before peak", tag: "DETECTED" },
      { text: "Back foot lands slightly off the bolts", tag: "DETECTED" },
      { text: "Pop height mid-range for flat ground", tag: "ESTIMATE" },
    ],
    breakdown: [
      { k: "Pop", v: 6.0 },
      { k: "Catch", v: 7.5 },
      { k: "Landing", v: 5.5 },
      { k: "Style", v: 7.0 },
    ],
    workOn:
      "Drive the back foot down with the catch instead of waiting for the board. You're catching early — trust it and stomp.",
    styleNote: "Solid. Shoulders stay square, no arm flail.",
  },
  "bs-5050": {
    trickOnFilm: "BS 50-50",
    abstained: false,
    rating: 7.0,
    verdict: "Locked in, clean exit.",
    observations: [
      { text: "Both trucks locked on the ledge for full length", tag: "DETECTED" },
      { text: "Slight lean adjustment mid-grind, recovered", tag: "DETECTED" },
      { text: "Ledge height around curb-and-a-half", tag: "ESTIMATE" },
    ],
    breakdown: [
      { k: "Ollie in", v: 6.0 },
      { k: "Lock-in", v: 7.5 },
      { k: "Exit", v: 7.5 },
      { k: "Style", v: 7.0 },
    ],
    workOn:
      "Approach speed is timid — you're ollieing up at the last second. Commit two pushes earlier and the lock-in gets smoother.",
    styleNote: "Good posture through the grind. Exit was buttery.",
  },
  "ollie-5": {
    trickOnFilm: "Ollie",
    abstained: true,
    rating: null,
    verdict: "Can't rate this one honestly.",
    observations: [
      { text: "Clean pop and level board over the set", tag: "DETECTED" },
      { text: "Footage cuts before the landing is visible", tag: "NO EVIDENCE" },
    ],
    breakdown: null,
    workOn:
      "Refilm with the full landing in frame. If it rode away like the pop suggests, this is a solid clip — but a rating without the landing would be a guess, and we don't guess.",
    styleNote: null,
  },
};

export function analyzeSample(clip: SampleClip, trickCalled: string): Analysis {
  const base = SCRIPTED[clip.id];
  const mismatch = trickCalled !== clip.canonical;
  const observations: Observation[] = mismatch
    ? [
        {
          text: `You called ${trickCalled.toLowerCase()} — footage shows a ${clip.canonical.toLowerCase()}. Analysis below is for what's on film.`,
          tag: "DETECTED",
        },
        ...base.observations,
      ]
    : base.observations;
  return { ...base, observations, trickCalled, mismatch, source: "sample" };
}

/**
 * Deterministic pseudo-random from a string, so the same clip gets the same
 * numbers on re-analysis — no dice-roll feedback.
 */
function seeded(str: string): number {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967295;
}

const FAMILY_BREAKDOWN = {
  flip: ["Pop", "Catch", "Landing", "Style"],
  grind: ["Ollie in", "Lock-in", "Exit", "Style"],
  air: ["Pop", "Level", "Landing", "Style"],
} as const;

function familyOf(trick: string): keyof typeof FAMILY_BREAKDOWN {
  if (["BS 50-50", "FS Boardslide"].includes(trick)) return "grind";
  if (["Ollie", "Nollie"].includes(trick)) return "air";
  return "flip";
}

/**
 * Honesty contract:
 * - The lite engine CANNOT see the footage, so it never emits DETECTED for
 *   user clips. Everything is an ESTIMATE and the copy says so.
 * - Clips under 2 seconds (or with unknown duration) abstain: NO RATING.
 */
export function analyzeUserClip(uri: string, durationSec: number | null, trickCalled: string): Analysis {
  if (durationSec === null || durationSec < 2) {
    return {
      trickCalled,
      trickOnFilm: null,
      mismatch: false,
      abstained: true,
      rating: null,
      verdict: "Can't rate this one honestly.",
      observations: [
        { text: "Clip is under 2 seconds — not enough footage to assess", tag: "NO EVIDENCE" },
      ],
      breakdown: null,
      workOn: "Refilm with the full run-up, trick, and ride-away in frame. Aim for 4–10 seconds.",
      styleNote: null,
      source: "user",
    };
  }

  const seed = seeded(uri + trickCalled);
  const rating = Math.round((4.5 + seed * 3.5) * 2) / 2; // 4.5–8.0, .5 steps
  const keys = FAMILY_BREAKDOWN[familyOf(trickCalled)];
  const breakdown = keys
    .map((k, i) => ({
      k,
      v: Math.round((rating + (seeded(uri + k) - 0.5) * 2 + (i === 3 ? 0.3 : 0)) * 2) / 2,
    }))
    .map((b) => ({ ...b, v: Math.min(9, Math.max(2, b.v)) }));

  const weakest = breakdown.reduce((a, b) => (b.v < a.v ? b : a));

  return {
    trickCalled,
    trickOnFilm: null, // honest: the lite engine did not verify the footage
    mismatch: false,
    abstained: false,
    rating,
    verdict: `Sample read for a ${trickCalled.toLowerCase()} — lite numbers, not a real read of your clip.`,
    observations: [
      {
        text: `Assuming the ${trickCalled.toLowerCase()} landed as called — LITE ENGINE can't verify footage`,
        tag: "ESTIMATE",
      },
      { text: `${weakest.k} scored lowest in this generated read`, tag: "ESTIMATE" },
    ],
    breakdown,
    workOn: `In the full app, this is where Pegasus tells you exactly what to fix. The LITE ENGINE flags ${weakest.k.toLowerCase()} as the sample focus.`,
    styleNote: null,
    source: "user",
  };
}
