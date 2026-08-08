/** OnFlow production tokens — presentation only. */

export const C = {
  charcoal: "#000000",
  charcoal900: "#000000",
  charcoal800: "#050505",
  charcoal2: "#0A0A0A",
  charcoal3: "#111111",
  charcoal4: "#1A1A1A",
  charcoal5: "#222222",

  volt: "#C8FF00",
  voltSoft: "#D4FF4A",
  voltDeep: "#A8D900",

  red: "#FF2D2D",
  redSoft: "#FF5555",
  redDeep: "#CC1F1F",

  amber: "#FFB020",
  amberSoft: "#FFC44D",

  offwhite: "#F5F5F5",
  dim: "#888888",
  muted: "#AAAAAA",

  aluminum: "#1A1A1A",
} as const;

export const F = {
  heading: "Rubik_800ExtraBold",
  bold: "Rubik_700Bold",
  medium: "Rubik_500Medium",
  body: "Rubik_400Regular",
  mono: "JetBrainsMono_500Medium",
  monoBold: "JetBrainsMono_700Bold",
} as const;

export const SPACE = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  "2xl": 32,
} as const;

/**
 * Geometry: sharp default. Pills are the exception.
 * small controls 2–4 · cards 4–6 · large surfaces 6–8 · pill only when semantic
 */
export const RADIUS = {
  xs: 2,
  sm: 4,
  md: 6,
  lg: 8,
  xl: 8,
  pill: 999,
} as const;

export function withOpacity(hex: string, opacity: number): string {
  const value = hex.replace("#", "");
  const channels = value.length === 3 ? value.split("").map((c) => c + c).join("") : value;
  const r = parseInt(channels.slice(0, 2), 16);
  const g = parseInt(channels.slice(2, 4), 16);
  const b = parseInt(channels.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}
