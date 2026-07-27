import React, { memo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { C, F, RADIUS, SPACE, withOpacity } from "../theme";

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
  heating_up: "Heating up",
  stalled: "Stalled",
  consistent: "Consistent",
  dialed: "Dialed",
  breakthrough_close: "Breakthrough close",
};

const COLOR: Record<MomentumState, string> = {
  heating_up: C.amber,
  stalled: C.dim,
  consistent: C.offwhite,
  dialed: C.voltSoft,
  breakthrough_close: C.amberSoft,
};

function MomentumChipComponent({ state, size = "md", testID }: MomentumChipProps) {
  const color = COLOR[state];
  const label = LABELS[state];
  const height = size === "sm" ? 20 : 24;

  return (
    <View
      testID={testID}
      accessibilityRole="text"
      accessibilityLabel={`Momentum: ${label}`}
      style={[
        styles.container,
        {
          minHeight: height,
          backgroundColor: withOpacity(color, 0.15),
          paddingHorizontal: SPACE.sm,
          gap: SPACE.xs,
        },
      ]}
    >
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={[styles.label, { color }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: RADIUS.pill,
  },
  dot: { width: 6, height: 6, borderRadius: 3 },
  label: {
    fontFamily: F.medium,
    fontSize: 11,
    lineHeight: 16,
  },
});

export const MomentumChip = memo(MomentumChipComponent);
