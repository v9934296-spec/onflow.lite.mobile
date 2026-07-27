import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
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
import { MomentumChip } from "../src/components/MomentumChip";
import { TrickCard } from "../src/components/TrickCard";
import {
  fetchProgressionOverview,
  fetchProgressionTimeline,
  fetchTrickStats,
  fetchWhatsNext,
  type ProgressionOverview,
  type ProgressionTimelineItem,
  type WhatsNextPayload,
} from "../src/api/progressionApi";
import { RatingLine } from "../src/charts";
import { adaptTrickStats, formatTrickDisplay } from "../src/yourFlowAdapter";
import { C, F, SPACE } from "../src/theme";
import { Card, Eyebrow, SkeletonLines, WeekRow } from "../src/ui";
import type { DaySlot } from "../src/progress";

function dateKey(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

export default function PteFlowScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<ProgressionOverview | null>(null);
  const [whatsNext, setWhatsNext] = useState<WhatsNextPayload | null>(null);
  const [timeline, setTimeline] = useState<ProgressionTimelineItem[]>([]);
  const [tricks, setTricks] = useState(adaptTrickStats([]));

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    const [ov, wn, tl, ts] = await Promise.all([
      fetchProgressionOverview(),
      fetchWhatsNext(),
      fetchProgressionTimeline(1, 20),
      fetchTrickStats(),
    ]);
    if (!ov.ok && !ts.ok) {
      setError(ov.ok === false ? ov.error.message : "Could not load PTE.");
      setLoading(false);
      setRefreshing(false);
      return;
    }
    setOverview(ov.ok ? ov.data : null);
    setWhatsNext(wn.ok ? wn.data : null);
    setTimeline(tl.ok ? tl.data.items : []);
    setTricks(ts.ok ? adaptTrickStats(ts.data) : []);
    setLoading(false);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const ratings = useMemo(
    () =>
      [...timeline]
        .reverse()
        .map((item) => item.best_pte_score)
        .filter((score): score is number => score != null)
        .slice(-12),
    [timeline],
  );

  const week = useMemo<DaySlot[]>(() => {
    const byDay = new Map<string, { attempted: boolean; landed: boolean }>();
    for (const item of timeline) {
      if (!item.ended_at) continue;
      const key = dateKey(new Date(item.ended_at));
      const current = byDay.get(key) ?? { attempted: false, landed: false };
      current.attempted = true;
      current.landed = current.landed || (item.best_pte_score != null && item.best_pte_score >= 6);
      byDay.set(key, current);
    }
    const slots: DaySlot[] = [];
    for (let daysAgo = 6; daysAgo >= 0; daysAgo--) {
      const d = new Date();
      d.setHours(12, 0, 0, 0);
      d.setDate(d.getDate() - daysAgo);
      const row = byDay.get(dateKey(d));
      slots.push({
        date: dateKey(d),
        label: d.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase(),
        status: row?.landed ? "landed" : row?.attempted ? "bailed" : "none",
      });
    }
    return slots;
  }, [timeline]);

  return (
    <View style={[s.screen, { paddingTop: insets.top + 12, paddingBottom: insets.bottom }]}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={s.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} tintColor={C.volt} />
        }
      >
        <View style={s.header}>
          <Text style={s.title}>PTE.Flow</Text>
          <Text style={s.sub}>Evidence, momentum, and what to fight next.</Text>
        </View>

        {loading ? (
          <Card>
            <SkeletonLines />
          </Card>
        ) : null}

        {error ? (
          <Card accent={C.red}>
            <Text style={s.error}>{error}</Text>
            <Pressable onPress={() => void load()}>
              <Text style={s.retry}>Tap to retry</Text>
            </Pressable>
          </Card>
        ) : null}

        {!loading && !error ? (
          <>
            {whatsNext ? (
              <Card accent={whatsNext.has_recommendation ? C.volt : C.muted}>
                <Eyebrow color={C.volt}>WHAT'S NEXT</Eyebrow>
                <Text style={s.cardTitle}>
                  {whatsNext.focus_trick
                    ? formatTrickDisplay(whatsNext.focus_trick)
                    : "Build the dataset"}
                </Text>
                <Text style={s.cardSub}>{whatsNext.message}</Text>
                {whatsNext.focus_drill ? (
                  <Text style={s.drill}>Drill: {whatsNext.focus_drill}</Text>
                ) : null}
                {whatsNext.focus_cue ? <Text style={s.cue}>Cue: {whatsNext.focus_cue}</Text> : null}
              </Card>
            ) : null}

            {overview ? (
              <Card>
                <Eyebrow>OVERVIEW</Eyebrow>
                <View style={s.metrics}>
                  <Metric label="Make rate" value={`${Math.round(overview.global_make_rate)}%`} />
                  <Metric label="Attempts" value={String(overview.total_attempts)} />
                  <Metric label="Tricks" value={String(overview.total_tricks_attempted)} />
                  <Metric label="Streak" value={String(overview.current_streak)} />
                </View>
              </Card>
            ) : null}

            <Card>
              <Eyebrow>THIS WEEK</Eyebrow>
              <WeekRow days={week} />
            </Card>

            {ratings.length > 1 ? (
              <Card>
                <Eyebrow>PTE TREND</Eyebrow>
                <RatingLine ratings={ratings} />
              </Card>
            ) : null}

            {tricks.length > 0 ? (
              <View style={s.section}>
                <Text style={s.sectionTitle}>TRICK MOMENTUM</Text>
                {tricks.slice(0, 8).map((trick) => (
                  <Card key={trick.trick_id} style={s.trickRow}>
                    <View style={{ flex: 1, gap: 6 }}>
                      <Text style={s.trickName}>{trick.display_name}</Text>
                      <Text style={s.trickMeta}>{trick.make_rate_pct}% make rate</Text>
                      {trick.momentum_state ? (
                        <MomentumChip state={trick.momentum_state} size="sm" />
                      ) : null}
                    </View>
                    <Text style={s.arrow}>→</Text>
                  </Card>
                ))}
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.cards}>
                  {tricks.slice(0, 6).map((trick) => (
                    <TrickCard key={`card-${trick.trick_id}`} trick={trick} onPress={() => undefined} />
                  ))}
                </ScrollView>
              </View>
            ) : (
              <Card>
                <Text style={s.cardSub}>No trick evidence yet. Film sessions to fill PTE.Flow.</Text>
              </Card>
            )}

            <Pressable onPress={() => router.push("/history" as never)}>
              <Text style={s.link}>Open full history →</Text>
            </Pressable>
          </>
        ) : null}
      </ScrollView>
      <AppNav />
    </View>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={s.metric}>
      <Text style={s.metricValue}>{value}</Text>
      <Text style={s.metricLabel}>{label}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  content: { paddingHorizontal: SPACE.lg, paddingBottom: SPACE.xl, gap: SPACE.lg },
  header: { gap: 8 },
  title: { fontFamily: F.heading, fontSize: 34, lineHeight: 38, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 14, lineHeight: 21, color: C.dim },
  error: { fontFamily: F.body, color: C.offwhite },
  retry: { fontFamily: F.bold, color: C.volt, marginTop: 8 },
  cardTitle: { fontFamily: F.heading, fontSize: 22, color: C.offwhite },
  cardSub: { fontFamily: F.body, fontSize: 14, lineHeight: 20, color: C.dim },
  drill: { fontFamily: F.medium, fontSize: 13, color: C.offwhite },
  cue: { fontFamily: F.mono, fontSize: 12, color: C.volt },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: SPACE.md },
  metric: { width: "45%", gap: 2 },
  metricValue: { fontFamily: F.monoBold, fontSize: 22, color: C.offwhite },
  metricLabel: { fontFamily: F.mono, fontSize: 11, color: C.dim, textTransform: "uppercase" },
  section: { gap: SPACE.md },
  sectionTitle: {
    fontFamily: F.medium,
    fontSize: 12,
    letterSpacing: 0.8,
    color: C.dim,
    textTransform: "uppercase",
  },
  trickRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  trickName: { fontFamily: F.bold, fontSize: 16, color: C.offwhite },
  trickMeta: { fontFamily: F.mono, fontSize: 11, color: C.dim },
  arrow: { fontFamily: F.bold, color: C.dim, fontSize: 18 },
  cards: { gap: SPACE.md },
  link: { fontFamily: F.bold, color: C.volt, fontSize: 14 },
});
