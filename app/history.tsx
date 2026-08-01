import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppNav } from "../src/components/AppNav";
import { track } from "../src/analytics";
import {
  fetchProgressionTimeline,
  type ProgressionTimelineItem,
} from "../src/api/progressionApi";
import { formatTrickDisplay } from "../src/progressionAdapter";
import { C, F, RADIUS, SPACE } from "../src/theme";
import { Btn, Card, Eyebrow, SkeletonLines } from "../src/ui";

function formatDate(iso: string | null): string {
  if (!iso) return "Recent";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Recent";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function SessionHistory() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [items, setItems] = useState<ProgressionTimelineItem[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (nextPage: number, mode: "replace" | "append" | "refresh") => {
    if (mode === "refresh") setRefreshing(true);
    else if (mode === "append") setLoadingMore(true);
    else setLoading(true);
    setError(null);

    const result = await fetchProgressionTimeline(nextPage, 20);
    if (!result.ok) {
      setError(result.error.message);
      setLoading(false);
      setLoadingMore(false);
      setRefreshing(false);
      return;
    }

    setItems((prev) => (mode === "append" ? [...prev, ...result.data.items] : result.data.items));
    setPage(result.data.page);
    setHasMore(result.data.has_more);
    setLoading(false);
    setLoadingMore(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    track("session_history_viewed");
    void load(1, "replace");
  }, [load]);

  return (
    <View style={[s.screen, { paddingTop: insets.top + 12, paddingBottom: insets.bottom }]}>
      <View style={s.content}>
        <View style={{ gap: 6 }}>
          <Eyebrow color={C.volt}>PROGRESSION</Eyebrow>
          <Text style={s.title}>History</Text>
          <Text style={s.sub}>Completed sessions with PTE evidence. Tap a row to reopen the recap.</Text>
        </View>

        {loading ? (
          <Card>
            <SkeletonLines />
          </Card>
        ) : error ? (
          <View style={s.centered}>
            <Text style={s.error}>{error}</Text>
            <Btn label="Retry" variant="ghost" onPress={() => void load(1, "replace")} />
          </View>
        ) : items.length === 0 ? (
          <Card accent={C.red}>
            <Eyebrow color={C.red}>NO SESSIONS</Eyebrow>
            <Text style={s.emptyTitle}>Go build the first one.</Text>
            <Text style={s.sub}>Finish a session and it will land here automatically.</Text>
            <Btn label="Start Flow" onPress={() => router.replace("/flow" as never)} />
          </Card>
        ) : (
          <ScrollView
            contentContainerStyle={{ gap: SPACE.sm, paddingBottom: 12 }}
            showsVerticalScrollIndicator={false}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={() => void load(1, "refresh")}
                tintColor={C.volt}
              />
            }
          >
            {items.map((item, index) => (
              <Pressable
                key={`${item.session_id}-${index}`}
                onPress={() => {
                  track("session_history_opened", { session_id: item.session_id });
                  router.push(`/recap?sessionId=${encodeURIComponent(item.session_id)}` as never);
                }}
                style={({ pressed }) => [s.row, pressed && { opacity: 0.72 }]}
              >
                <View style={{ flex: 1, gap: 4 }}>
                  <Text style={s.rowTitle}>
                    {item.focus_trick
                      ? formatTrickDisplay(item.focus_trick)
                      : item.spot ?? "Session"}
                  </Text>
                  <Text style={s.rowSub}>
                    {formatDate(item.ended_at)}
                    {item.best_pte_score != null ? ` · PTE ${item.best_pte_score}` : ""}
                    {item.clips_count ? ` · ${item.clips_count} clips` : ""}
                  </Text>
                </View>
                <Text style={s.chevron}>›</Text>
              </Pressable>
            ))}
            {hasMore ? (
              <Btn
                label={loadingMore ? "Loading…" : "Load more"}
                variant="ghost"
                loading={loadingMore}
                onPress={() => void load(page + 1, "append")}
              />
            ) : null}
          </ScrollView>
        )}

        <Btn label="Back" variant="ghost" onPress={() => router.back()} />
      </View>
      <AppNav />
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  content: { flex: 1, paddingHorizontal: SPACE.lg, gap: SPACE.md },
  title: { fontFamily: F.heading, fontSize: 32, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", gap: 8 },
  emptyTitle: { fontFamily: F.bold, fontSize: 17, color: C.offwhite },
  error: { fontFamily: F.body, fontSize: 13, lineHeight: 18, color: C.red, textAlign: "center" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderRadius: RADIUS.lg,
    paddingHorizontal: 14,
    paddingVertical: 14,
    backgroundColor: C.charcoal2,
    borderLeftWidth: 3,
    borderLeftColor: C.volt,
  },
  rowTitle: { fontFamily: F.bold, fontSize: 15, color: C.offwhite },
  rowSub: { fontFamily: F.body, fontSize: 12, color: C.dim },
  chevron: { fontFamily: F.body, fontSize: 24, color: C.dim },
});
