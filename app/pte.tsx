import React, { useMemo } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppNav } from "../src/components/AppNav";
import { RatingLine } from "../src/charts";
import { getBestTrickStreak, getLast7Days } from "../src/progress";
import { useSession } from "../src/session";
import { C, F } from "../src/theme";
import { Card, Eyebrow, WeekRow } from "../src/ui";

function pct(n: number, d: number): string {
  return d > 0 ? `${Math.round((n / d) * 100)}%` : "—";
}

export default function PteFlowScreen() {
  const insets = useSafeAreaInsets();
  const { log, attempts } = useSession();

  const ratings = useMemo(
    () => log.filter((entry) => entry.analysis.source === "user" && entry.analysis.rating != null).map((entry) => entry.analysis.rating as number).slice(-12),
    [log],
  );
  const week = useMemo(() => getLast7Days(attempts), [attempts]);
  const bestStreak = useMemo(() => getBestTrickStreak(attempts), [attempts]);
  const stats = useMemo(() => {
    const total = attempts.reduce((sum, a) => sum + Math.max(a.attempts || 1, 1), 0);
    const landed = attempts.filter((a) => a.manualOutcome === "landed" || a.landed).length;
    const byTrick = new Map<string, { entries: number; lands: number }>();
    for (const a of attempts) {
      const row = byTrick.get(a.trick) ?? { entries: 0, lands: 0 };
      row.entries += 1;
      if (a.manualOutcome === "landed" || a.landed) row.lands += 1;
      byTrick.set(a.trick, row);
    }
    const tricks = [...byTrick.entries()]
      .map(([trick, row]) => ({ trick, ...row }))
      .sort((a, b) => b.entries - a.entries)
      .slice(0, 5);
    return { total, landed, entries: attempts.length, tricks };
  }, [attempts]);

  return (
    <View style={[s.screen, { paddingTop: insets.top + 12, paddingBottom: insets.bottom }]}> 
      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
        <View style={s.header}>
          <Eyebrow color={C.volt}>PTE.FLOW</Eyebrow>
          <Text style={s.title}>Progress you can prove.</Text>
          <Text style={s.sub}>Manual attempts track consistency. Video-derived PTE ratings stay separate and only appear when the analysis has usable evidence.</Text>
        </View>

        <View style={s.metricRow}>
          <View style={s.metric}><Text style={s.metricValue}>{stats.entries}</Text><Text style={s.metricLabel}>LOGGED</Text></View>
          <View style={s.metric}><Text style={s.metricValue}>{stats.landed}</Text><Text style={s.metricLabel}>LANDS</Text></View>
          <View style={s.metric}><Text style={s.metricValue}>{pct(stats.landed, stats.entries)}</Text><Text style={s.metricLabel}>LAND RATE</Text></View>
        </View>

        <Card accent={C.volt}>
          <Eyebrow color={C.volt}>CONSISTENCY / LAST 7 DAYS</Eyebrow>
          <WeekRow days={week} />
          <Text style={s.note}>Green = at least one reported land. Pink = attempts logged without a land. This is habit data, not a PTE score.</Text>
        </Card>

        <Card>
          <Eyebrow color={C.volt}>VIDEO PTE TREND</Eyebrow>
          {ratings.length ? (
            <>
              <RatingLine ratings={ratings} />
              <Text style={s.note}>Only ratings returned from analyzed user clips are plotted. No clip evidence means no invented score.</Text>
            </>
          ) : (
            <View style={s.empty}>
              <Text style={s.emptyTitle}>No video-rated attempts yet.</Text>
              <Text style={s.note}>Film attempts from Flow. When the clip supports a rating, the trend appears here automatically.</Text>
            </View>
          )}
        </Card>

        <View style={{ gap: 10 }}>
          <Eyebrow>MOST WORKED TRICKS</Eyebrow>
          {stats.tricks.length ? stats.tricks.map((row, index) => (
            <View key={row.trick} style={s.trickRow}>
              <Text style={s.rank}>{String(index + 1).padStart(2, "0")}</Text>
              <View style={{ flex: 1 }}><Text style={s.trickName}>{row.trick}</Text><Text style={s.note}>{row.entries} logs · {row.lands} landed</Text></View>
              <Text style={s.trickRate}>{pct(row.lands, row.entries)}</Text>
            </View>
          )) : <Text style={s.note}>Log a few attempts in Flow and your trick progression will build here.</Text>}
        </View>

        {bestStreak ? (
          <Card accent={C.red}>
            <Eyebrow color={C.red}>CURRENT MOMENTUM</Eyebrow>
            <Text style={s.focus}>{bestStreak.trick}</Text>
            <Text style={s.sub}>{bestStreak.streak}-day landing streak. Keep the reps honest and let the evidence accumulate.</Text>
          </Card>
        ) : null}
      </ScrollView>
      <AppNav />
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  content: { paddingHorizontal: 24, paddingTop: 16, paddingBottom: 28, gap: 18 },
  header: { gap: 8 },
  title: { fontFamily: F.heading, fontSize: 34, lineHeight: 38, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 14, lineHeight: 21, color: C.dim },
  metricRow: { flexDirection: "row", gap: 8 },
  metric: { flex: 1, backgroundColor: C.charcoal2, borderRadius: 12, paddingVertical: 14, paddingHorizontal: 10 },
  metricValue: { fontFamily: F.heading, fontSize: 23, color: C.offwhite },
  metricLabel: { fontFamily: F.mono, fontSize: 9, letterSpacing: 0.8, color: C.dim, marginTop: 3 },
  note: { fontFamily: F.body, fontSize: 12, lineHeight: 18, color: C.dim },
  empty: { paddingVertical: 14, gap: 5 },
  emptyTitle: { fontFamily: F.bold, fontSize: 15, color: C.offwhite },
  trickRow: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: C.charcoal2, borderRadius: 12, padding: 14 },
  rank: { fontFamily: F.mono, color: C.red, fontSize: 11 },
  trickName: { fontFamily: F.bold, color: C.offwhite, fontSize: 15 },
  trickRate: { fontFamily: F.heading, color: C.volt, fontSize: 18 },
  focus: { fontFamily: F.heading, fontSize: 26, color: C.offwhite, marginTop: 4 },
});
