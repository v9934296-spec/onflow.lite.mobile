import React, { memo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { MomentumChip, type MomentumState } from "./MomentumChip";
import { C, F, RADIUS, SPACE, withOpacity } from "../theme";

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
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={`${trick.display_name} trick card`}
      onPress={onPress}
      style={({ pressed }) => [styles.container, pressed && { opacity: 0.9 }]}
    >
      {trick.battle_status === "active" ? (
        <View style={[styles.battleChip, { backgroundColor: withOpacity(C.red, 0.2) }]}>
          <Text style={[styles.battleText, { color: C.red }]}>BATTLE</Text>
        </View>
      ) : trick.battle_status === "won" ? (
        <View style={[styles.battleChip, { backgroundColor: withOpacity(C.volt, 0.2) }]}>
          <Text style={[styles.battleText, { color: C.volt }]}>WON</Text>
        </View>
      ) : null}
      <Text style={styles.name} numberOfLines={2}>
        {trick.display_name}
      </Text>
      <Text style={styles.rate}>{trick.make_rate_pct}%</Text>
      <Text style={styles.caption}>make rate</Text>
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
    borderRadius: RADIUS.lg,
    padding: SPACE.md,
    gap: SPACE.sm,
  },
  battleChip: {
    alignSelf: "flex-start",
    borderRadius: RADIUS.pill,
    paddingHorizontal: SPACE.sm,
    paddingVertical: 2,
  },
  battleText: { fontFamily: F.bold, fontSize: 10, letterSpacing: 0.8 },
  name: { fontFamily: F.bold, fontSize: 16, color: C.offwhite, lineHeight: 20 },
  rate: { fontFamily: F.monoBold, fontSize: 28, color: C.volt },
  caption: { fontFamily: F.mono, fontSize: 10, color: C.dim },
});

export const TrickCard = memo(TrickCardComponent);
