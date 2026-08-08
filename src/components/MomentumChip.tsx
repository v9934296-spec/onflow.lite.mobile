import React, { memo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { C, F, SPACE } from "../theme";

export type MomentumState =
  | "heating_up"
  | "stalled"
  | "consistent"
  | "dialed"
  | "breakthrough_close";

export type MomentumChipProps = {
  state: MomentumState;
  size?: "sm" | "md";
  testID?: string;
};

const LABELS: Record<MomentumState, string> = {
  heating_up: "↑ HEATING UP",
  stalled: "STALLED",
  consistent: "CONSISTENT",
  dialed: "DIALED",
  breakthrough_close: "↗ BREAKTHROUGH CLOSE",
};

const COLOR: Record<MomentumState, string> = {
  heating_up: C.amber,
  stalled: C.dim,
  consistent: C.offwhite,
  dialed: C.volt,
  breakthrough_close: C.amberSoft,
};

function MomentumChipComponent({ state, size = "md", testID }: MomentumChipProps) {
  const color = COLOR[state];
  const label = LABELS[state];

  return (
    <View
      testID={testID}
      accessibilityRole="text"
      accessibilityLabel={`Momentum: ${label}`}
      style={[styles.container, size === "sm" ? styles.sm : null]}
    >
      <View style={[styles.edge, { backgroundColor: color }]} />
      <Text style={[styles.label, { color, fontSize: size === "sm" ? 10 : 11 }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: SPACE.sm,
  },
  sm: { gap: 6 },
  edge: { width: 2, alignSelf: "stretch", minHeight: 12 },
  label: {
    fontFamily: F.bold,
    letterSpacing: 0.8,
    lineHeight: 16,
  },
});

export const MomentumChip = memo(MomentumChipComponent);
