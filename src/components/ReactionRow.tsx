import React, { memo, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import type { ReactionsSummary, ReactionType } from "../types/feedEvent";
import { C, F, RADIUS, SPACE, withOpacity } from "../theme";

export type ReactionRowProps = {
  reactionsSummary: ReactionsSummary;
  onReact: (reactionType: ReactionType) => void;
  testID?: string;
};

const ORDER: ReadonlyArray<{ type: ReactionType; emoji: string; label: string }> = [
  { type: "fire", emoji: "🔥", label: "Fire" },
  { type: "saw_it", emoji: "👁", label: "Saw it" },
  { type: "same_battle", emoji: "🤝", label: "Same battle" },
  { type: "progression", emoji: "📈", label: "Progression" },
];

const TINT: Record<ReactionType, string> = {
  fire: withOpacity(C.amber, 0.2),
  saw_it: withOpacity(C.dim, 0.3),
  same_battle: withOpacity(C.red, 0.2),
  progression: withOpacity(C.volt, 0.2),
};

function ReactionRowComponent({ reactionsSummary, onReact, testID }: ReactionRowProps) {
  const [localSummary, setLocalSummary] = useState(reactionsSummary);

  useEffect(() => {
    setLocalSummary(reactionsSummary);
  }, [reactionsSummary]);

  const handleReact = (reactionType: ReactionType) => {
    setLocalSummary((prev) => {
      const current = prev[reactionType];
      const nextBucket = current.viewer_reacted
        ? { ...current, viewer_reacted: false, count: Math.max(0, current.count - 1) }
        : { ...current, viewer_reacted: true, count: current.count + 1 };
      return { ...prev, [reactionType]: nextBucket };
    });
    onReact(reactionType);
  };

  return (
    <View testID={testID} style={styles.row}>
      {ORDER.map((item) => {
        const bucket = localSummary[item.type];
        return (
          <Pressable
            key={item.type}
            accessibilityRole="button"
            accessibilityLabel={item.label}
            onPress={() => handleReact(item.type)}
            style={[
              styles.btn,
              bucket.viewer_reacted && { backgroundColor: TINT[item.type] },
            ]}
          >
            <Text style={styles.emoji}>{item.emoji}</Text>
            {bucket.count > 0 ? <Text style={styles.count}>{bucket.count}</Text> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", gap: SPACE.sm, flexWrap: "wrap" },
  btn: {
    minHeight: 36,
    paddingHorizontal: SPACE.sm,
    borderRadius: RADIUS.md,
    backgroundColor: C.charcoal3,
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  emoji: { fontSize: 14 },
  count: { fontFamily: F.mono, fontSize: 11, color: C.offwhite },
});

export const ReactionRow = memo(ReactionRowComponent);
