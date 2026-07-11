import { Analysis, EvidenceClass, Observation, Receipt, SampleClip } from "./types";

export const ENGINE_VERSION = "pte-lite-v0.1";
export const MIN_CLIP_DURATION_SEC = 2;
export const MIN_CONFIDENCE_FOR_RATING = 50;

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

type AnalysisCore = Omit<
  Analysis,
  "trickCalled" | "mismatch" | "source" | "engineVersion" | "evidenceClass" | "confidence" | "receipts" | "abstainReason"
>;

const SCRIPTED: Record<string, AnalysisCore> = {
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

export function computeConfidence(observations: Observation[]): number {
  if (observations.length === 0) return 0;
  let score = 0;
  for (const o of observations) {
    if (o.tag === "DETECTED") score += 100;
    else if (o.tag === "ESTIMATE") score += 40;
  }
  return Math.round(score / observations.length);
}

export function deriveEvidenceClass(
  observations: Observation[],
  source: "sample" | "user",
): EvidenceClass {
  if (source === "user") {
    if (observations.some((o) => o.tag === "DETECTED")) {
      console.warn("P.T.E. invariant violation: DETECTED user observation clamped to ESTIMATE");
    }
    return observations.some((o) => o.tag !== "NO EVIDENCE") ? "ESTIMATE" : "NO EVIDENCE";
  }
  if (observations.some((o) => o.tag === "DETECTED")) return "DETECTED";
  if (observations.some((o) => o.tag === "ESTIMATE")) return "ESTIMATE";
  return "NO EVIDENCE";
}

export function buildReceiptsFromObservations(observations: Observation[]): Receipt[] {
  return observations.map((o, i) => ({
    id: `obs-${i}`,
    label: o.tag,
    source:
      o.tag === "DETECTED" ? "detected" : o.tag === "ESTIMATE" ? "estimated" : "none",
    detail: o.text,
  }));
}

export function buildReceiptsFromBreakdown(breakdown: Analysis["breakdown"]): Receipt[] {
  if (!breakdown) return [];
  return breakdown.map((b) => ({
    id: `bd-${b.k}`,
    label: b.k,
    source: "detected" as const,
    detail: `${b.k} scored ${b.v.toFixed(1)} / 10 in scripted sample analysis`,
  }));
}

function finalizeAnalysis(
  core: AnalysisCore,
  opts: {
    trickCalled: string;
    mismatch: boolean;
    source: "sample" | "user";
    observations: Observation[];
    extraReceipts?: Receipt[];
    abstainReason?: string | null;
    confidenceOverride?: number;
  },
): Analysis {
  const observations = opts.observations;
  let confidence = opts.confidenceOverride ?? computeConfidence(observations);
  let abstained = core.abstained;
  let rating = core.rating;
  let abstainReason = opts.abstainReason ?? (core.abstained ? core.workOn : null);

  if (!abstained && rating !== null && confidence < MIN_CONFIDENCE_FOR_RATING) {
    abstained = true;
    rating = null;
    abstainReason = `Confidence ${confidence}% is below the ${MIN_CONFIDENCE_FOR_RATING}% threshold required to publish a rating.`;
  }

  const evidenceClass = deriveEvidenceClass(observations, opts.source);
  const receipts = [
    ...(opts.extraReceipts ?? []),
    ...buildReceiptsFromObservations(observations),
    ...buildReceiptsFromBreakdown(abstained ? null : core.breakdown),
    {
      id: "engine-version",
      label: "Engine",
      source: "measured" as const,
      detail: `Analysis produced by ${ENGINE_VERSION}`,
    },
  ];

  return {
    ...core,
    observations,
    trickCalled: opts.trickCalled,
    mismatch: opts.mismatch,
    source: opts.source,
    abstained,
    rating,
    engineVersion: ENGINE_VERSION,
    evidenceClass,
    confidence,
    receipts,
    abstainReason,
  };
}

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

  const abstainReason = base.abstained
    ? "Footage cuts before the landing is visible — rating would require guessing."
    : null;

  return finalizeAnalysis(base, {
    trickCalled,
    mismatch,
    source: "sample",
    observations,
    extraReceipts: [
      {
        id: "sample-clip",
        label: "Sample clip",
        source: "measured",
        detail: `${clip.label} · ${clip.durationSec}s · ${clip.spot}`,
      },
    ],
    abstainReason,
  });
}

function durationConfidence(durationSec: number): number {
  if (durationSec < MIN_CLIP_DURATION_SEC) return 0;
  if (durationSec < 4) return 15;
  if (durationSec <= 10) return 25;
  return 20;
}

/**
 * User footage: never DETECTED without a real pipeline. Evidence class is ESTIMATE.
 * Abstains when duration is insufficient. No invented ratings.
 */
export function analyzeUserClip(_uri: string, durationSec: number | null, trickCalled: string): Analysis {
  if (durationSec === null || durationSec < MIN_CLIP_DURATION_SEC) {
    const observations: Observation[] = [
      {
        text:
          durationSec === null
            ? "Clip duration unknown — not enough metadata to assess"
            : `Clip is ${durationSec.toFixed(1)}s — under ${MIN_CLIP_DURATION_SEC}s minimum`,
        tag: "NO EVIDENCE",
      },
    ];
    return finalizeAnalysis(
      {
        trickOnFilm: null,
        abstained: true,
        rating: null,
        verdict: "Can't rate this one honestly.",
        observations,
        breakdown: null,
        workOn: "Refilm with the full run-up, trick, and ride-away in frame. Aim for 4–10 seconds.",
        styleNote: null,
      },
      {
        trickCalled,
        mismatch: false,
        source: "user",
        observations,
        extraReceipts: [
          {
            id: "duration",
            label: "Clip duration",
            source: "measured",
            detail: durationSec === null ? "Unknown" : `${durationSec.toFixed(1)}s`,
          },
        ],
        abstainReason: "Insufficient clip duration for any assessment.",
      },
    );
  }

  const observations: Observation[] = [
    {
      text: `${durationSec.toFixed(1)}s clip — duration measured from file metadata`,
      tag: "ESTIMATE",
    },
    {
      text: "No video detection pipeline connected — trick outcome must be self-reported",
      tag: "NO EVIDENCE",
    },
  ];

  return finalizeAnalysis(
    {
      trickOnFilm: null,
      abstained: false,
      rating: null,
      verdict: "Log what happened — we can't read your clip yet.",
      observations,
      breakdown: null,
      workOn: "Record the attempt, spot, and outcome below. That's your honest session record.",
      styleNote: null,
      selfReportOnly: true,
    },
    {
      trickCalled,
      mismatch: false,
      source: "user",
      observations,
      extraReceipts: [
        {
          id: "duration",
          label: "Clip duration",
          source: "measured",
          detail: `${durationSec.toFixed(1)}s measured from file metadata`,
        },
        {
          id: "vision",
          label: "Video analysis",
          source: "none",
          detail: "No detection pipeline — evidence class ESTIMATE, outcome self-reported",
        },
      ],
      confidenceOverride: durationConfidence(durationSec),
    },
  );
}
