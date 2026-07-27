/** OnFlow production tokens harvested from onflow.skate — presentation only. */

export const C = {
  charcoal: "#1A1A1C",
  charcoal900: "#0E0E10",
  charcoal800: "#15151A",
  charcoal2: "#242428",
  charcoal3: "#2E2E33",
  charcoal4: "#3A3A40",
  charcoal5: "#5C5C66",
  volt: "#B8F035",
  voltSoft: "#CDF768",
  voltDeep: "#94C12A",
  red: "#D42B2B",
  redSoft: "#E55555",
  redDeep: "#A82020",
  amber: "#D4A03A",
  amberSoft: "#E4B85C",
  offwhite: "#F0EDED",
  dim: "#8A8A94",
  muted: "#B8B8C0",
  /** @deprecated prototype outline — do not use on product surfaces */
  aluminum: "#3A3A40",
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

export const RADIUS = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 16,
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
