import React, { memo, useEffect, useRef, useState } from "react";
import { AccessibilityInfo, Animated, Image, Pressable, StyleSheet, Text, View } from "react-native";
import { ReactionRow } from "./ReactionRow";
import { formatEventHeadline } from "../feed/formatHeadline";
import type { FeedEvent, ReactionType } from "../types/feedEvent";
import { C, F, RADIUS, SPACE } from "../theme";
import { Card } from "../ui";

export type FeedCardProps = {
  event: FeedEvent;
  onCardPress?: () => void;
  onReact?: (reactionType: ReactionType) => void;
  showReactions?: boolean;
  testID?: string;
};

const celebrated = new Set<string>();

function relativeTime(iso: string): string {
  const mins = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

function thumbnailFor(event: FeedEvent): string | null {
  const p = event.payload as unknown as Record<string, unknown>;
  for (const key of ["clip_thumbnail_url", "first_land_clip_thumbnail_url", "composite_url"]) {
    const v = p[key];
    if (typeof v === "string" && v) return v;
  }
  return null;
}

const EDGE: Record<FeedEvent["event_type"], string> = {
  first_land: C.volt,
  make_rate_jump: C.volt,
  battle_started: C.red,
  battle_won: C.volt,
  comparison_surfaced: C.amber,
  session_recap: C.muted,
};

function FeedCardComponent({
  event,
  onCardPress,
  onReact,
  showReactions = true,
  testID,
}: FeedCardProps) {
  const [summary, setSummary] = useState(event.reactions_summary);
  const shouldCelebrate =
    event.event_type === "battle_won" && !celebrated.has(event.id);
  const progress = useRef(new Animated.Value(shouldCelebrate ? 0 : 1)).current;

  useEffect(() => {
    setSummary(event.reactions_summary);
  }, [event.reactions_summary]);

  useEffect(() => {
    if (shouldCelebrate) celebrated.add(event.id);
  }, [shouldCelebrate, event.id]);

  useEffect(() => {
    if (!shouldCelebrate) return;
    void AccessibilityInfo.isReduceMotionEnabled().then((enabled) => {
      if (enabled) {
        progress.setValue(1);
        return;
      }
      Animated.timing(progress, {
        toValue: 1,
        duration: 600,
        useNativeDriver: true,
      }).start();
    });
  }, [shouldCelebrate, progress]);

  const displayName = event.user.tag_name || event.user.username;
  const thumb = thumbnailFor(event);
  const headline = formatEventHeadline(event);

  return (
    <Animated.View style={{ opacity: progress, transform: [{ scale: progress.interpolate({ inputRange: [0, 1], outputRange: [0.96, 1] }) }] }}>
      <Card accent={EDGE[event.event_type]} onPress={onCardPress} style={styles.card}>
        <View testID={testID} style={styles.inner}>
          <View style={styles.authorRow}>
            <View style={styles.avatar}>
              {event.user.profile_photo_url ? (
                <Image source={{ uri: event.user.profile_photo_url }} style={styles.avatarImg} />
              ) : (
                <Text style={styles.avatarLetter}>{displayName.slice(0, 1).toUpperCase()}</Text>
              )}
            </View>
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={styles.author}>{displayName}</Text>
              <Text style={styles.time}>{relativeTime(event.generated_at)}</Text>
            </View>
          </View>
          <Text style={styles.headline}>{headline}</Text>
          {thumb ? (
            <Image source={{ uri: thumb }} style={styles.thumb} accessibilityLabel="Clip thumbnail" />
          ) : null}
          {showReactions && onReact ? (
            <ReactionRow
              reactionsSummary={summary}
              onReact={(type) => {
                setSummary((prev) => {
                  const current = prev[type];
                  const next = current.viewer_reacted
                    ? { ...current, viewer_reacted: false, count: Math.max(0, current.count - 1) }
                    : { ...current, viewer_reacted: true, count: current.count + 1 };
                  return { ...prev, [type]: next };
                });
                onReact(type);
              }}
            />
          ) : null}
        </View>
      </Card>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  card: { paddingLeft: SPACE.lg + 4 },
  inner: { gap: SPACE.md },
  authorRow: { flexDirection: "row", alignItems: "center", gap: SPACE.sm },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: C.charcoal3,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  avatarImg: { width: 36, height: 36 },
  avatarLetter: { fontFamily: F.bold, color: C.offwhite, fontSize: 14 },
  author: { fontFamily: F.bold, fontSize: 14, color: C.offwhite },
  time: { fontFamily: F.mono, fontSize: 11, color: C.dim },
  headline: { fontFamily: F.body, fontSize: 15, lineHeight: 22, color: C.offwhite },
  thumb: {
    width: "100%",
    height: 160,
    borderRadius: RADIUS.md,
    backgroundColor: C.charcoal3,
  },
});

export const FeedCard = memo(FeedCardComponent);
