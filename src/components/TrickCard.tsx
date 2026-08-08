import React, { memo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { MomentumChip, type MomentumState } from "./MomentumChip";
import { C, F, RADIUS, SPACE } from "../theme";

export type TrickSummary = {
  trick_id: string;
  display_name: string;
  make_rate_pct: number;
  last_clip_at: string;
  battle_status: "active" | "won" | "dormant" | "none";
  momentum_state: MomentumState | null;
};

export type TrickCardProps = {
  trick: TrickSummary;
  onPress: () => void;
  showMomentum?: boolean;
  testID?: string;
};

function TrickCardComponent({ trick, onPress, showMomentum = true, testID }: TrickCardProps) {
  const battleLabel =
    trick.battle_status === "active"
      ? "BATTLE //"
      : trick.battle_status === "won"
        ? "WON //"
        : null;

  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={`${trick.display_name} trick card`}
      onPress={onPress}
      style={({ pressed }) => [styles.container, pressed && { opacity: 0.9, transform: [{ scale: 0.98 }] }]}
    >
      <View style={styles.cut} />
      {battleLabel ? (
        <Text
          style={[
            styles.battleText,
            { color: trick.battle_status === "active" ? C.red : C.volt },
          ]}
        >
          {battleLabel}
        </Text>
      ) : (
        <Text style={styles.battlePlaceholder}> </Text>
      )}
      <Text style={styles.name} numberOfLines={2}>
        {trick.display_name.toUpperCase()}
      </Text>
      <View style={styles.sep} />
      <Text style={styles.rate}>{trick.make_rate_pct}%</Text>
      <Text style={styles.caption}>LAND RATE</Text>
      {showMomentum && trick.momentum_state ? (
        <MomentumChip state={trick.momentum_state} size="sm" />
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    width: 160,
    minHeight: 180,
    backgroundColor: C.charcoal2,
    borderRadius: RADIUS.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.charcoal5,
    padding: SPACE.md,
    gap: SPACE.sm,
    overflow: "hidden",
  },
  /** Clipped / cut top-right corner */
  cut: {
    position: "absolute",
    top: 0,
    right: 0,
    width: 0,
    height: 0,
    borderStyle: "solid",
    borderTopWidth: 14,
    borderLeftWidth: 14,
    borderTopColor: C.charcoal,
    borderLeftColor: "transparent",
  },
  battleText: {
    fontFamily: F.monoBold,
    fontSize: 10,
    letterSpacing: 1,
  },
  battlePlaceholder: { fontFamily: F.mono, fontSize: 10, height: 12 },
  name: {
    fontFamily: F.heading,
    fontSize: 18,
    color: C.offwhite,
    lineHeight: 22,
    letterSpacing: 0.3,
  },
  sep: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: C.charcoal5,
    marginVertical: 2,
  },
  rate: { fontFamily: F.monoBold, fontSize: 34, color: C.volt, lineHeight: 36 },
  caption: {
    fontFamily: F.mono,
    fontSize: 10,
    color: C.dim,
    letterSpacing: 1,
  },
});

export const TrickCard = memo(TrickCardComponent);
