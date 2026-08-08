import React, { memo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { MomentumChip, type MomentumState } from "./MomentumChip";
import { C, F, SPACE } from "../theme";

export type CurrentFocus = {
  trick_id: string | null;
  display_name: string | null;
  battle_duration_days: number | null;
  last_session_summary: {
    delta_summary: string;
    delta_type: "make_rate_jump" | "first_land" | "battle_started" | "session_completed";
  } | null;
  momentum_state: MomentumState | null;
  empty_state?: "no_active_battle" | "no_clips";
};

export type CurrentFocusHeaderProps = {
  focus: CurrentFocus;
  onPress?: () => void;
  testID?: string;
};

function CurrentFocusHeaderComponent({ focus, onPress, testID }: CurrentFocusHeaderProps) {
  const populated = focus.trick_id !== null && focus.display_name !== null;

  if (!populated) {
    const text =
      focus.empty_state === "no_clips"
        ? "Your focus trick will appear here once you start filming."
        : "Your focus trick will appear here once you start battling something.";
    return (
      <View testID={testID} style={styles.container}>
        <Text style={styles.eyebrow}>CURRENT FOCUS</Text>
        <Text style={styles.empty}>{text}</Text>
      </View>
    );
  }

  const body = (
    <View testID={testID} style={styles.container}>
      <Text style={styles.eyebrow}>CURRENT FOCUS</Text>
      <Text style={styles.title}>{focus.display_name.toUpperCase()}</Text>
      <View style={styles.metaRow}>
        {focus.battle_duration_days != null ? (
          <Text style={styles.meta}>DAY {focus.battle_duration_days}</Text>
        ) : null}
        {focus.momentum_state ? <MomentumChip state={focus.momentum_state} size="sm" /> : null}
      </View>
      {focus.last_session_summary ? (
        <Text style={styles.summary}>{focus.last_session_summary.delta_summary}</Text>
      ) : null}
    </View>
  );

  if (!onPress) return body;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [{ opacity: pressed ? 0.9 : 1 }]}>
      {body}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingVertical: SPACE.xl,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.charcoal3,
    gap: SPACE.sm,
  },
  eyebrow: {
    fontFamily: F.medium,
    fontSize: 11,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    color: C.muted,
  },
  empty: { fontFamily: F.body, fontSize: 15, lineHeight: 22, color: C.dim },
  title: { fontFamily: F.heading, fontSize: 28, lineHeight: 32, color: C.offwhite },
  metaRow: { flexDirection: "row", alignItems: "center", gap: SPACE.sm, flexWrap: "wrap" },
  meta: { fontFamily: F.mono, fontSize: 12, color: C.red },
  summary: { fontFamily: F.body, fontSize: 14, lineHeight: 20, color: C.dim },
});

export const CurrentFocusHeader = memo(CurrentFocusHeaderComponent);
