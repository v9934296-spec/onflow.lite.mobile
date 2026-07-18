import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppNav } from "../src/components/AppNav";
import { fetchProgressionTimeline, type ProgressionTimelineItem } from "../src/api/progressionApi";
import { RatingLine } from "../src/charts";
import type { DaySlot } from "../src/progress";
import { useSession } from "../src/session";
import { useSkateSession } from "../src/skateSession/skateSessionContext";
import { useSessionHistory } from "../src/sessionHistory/useSessionHistory";
import { C, F } from "../src/theme";
import { Card, Eyebrow, WeekRow } from "../src/ui";

function pct(n: number, d: number): string { return d > 0 ? `${Math.round((n / d) * 100)}%` : "—"; }
function dateKey(value: Date): string { return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`; }
function shortDate(value: string | null): string {
  if (!value) return "Recent";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "Recent" : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export default function PteFlowScreen() {
  const insets = useSafeAreaInsets();
  const { log } = useSession();
  const { activeSession } = useSkateSession();
  const { sessions } = useSessionHistory(activeSession?.id ?? null);
  const [timeline, setTimeline] = useState<ProgressionTimelineItem[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(true);
  const [timelineError, setTimelineError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setTimelineLoading(true);
    void fetchProgressionTimeline(1, 20).then((result) => {
      if (cancelled) return;
      if (result.ok) { setTimeline(result.data.items); setTimelineError(null); }
      else setTimelineError(result.error.message);
      setTimelineLoading(false);
    });
    return () => { cancelled = true; };
  }, []);

  const localRatings = useMemo(() => log.filter((entry) => entry.analysis.source === "user" && entry.analysis.rating != null).map((entry) => entry.analysis.rating as number).slice(-12), [log]);
  const backendRatings = useMemo(() => [...timeline].reverse().map((item) => item.best_pte_score).filter((score): score is number => score != null).slice(-12), [timeline]);
  const ratings = backendRatings.length ? backendRatings : localRatings;

  const stats = useMemo(() => {
    let total = 0;
    let landed = 0;
    const byTrick = new Map<string, { entries: number; lands: number }>();
    for (const session of sessions) {
      total += session.attempts_count;
      landed += session.landed_count;
      for (const row of session.trick_breakdown) {
        const current = byTrick.get(row.canonicalName) ?? { entries: 0, lands: 0 };
        current.entries += row.total;
        current.lands += row.landed;
        byTrick.set(row.canonicalName, current);
      }
    }
    const tricks = [...byTrick.entries()].map(([trick, row]) => ({ trick, ...row })).sort((a, b) => b.entries - a.entries).slice(0, 5);
    return { total, landed, tricks };
  }, [sessions]);

  const week = useMemo<DaySlot[]>(() => {
    const sessionByDay = new Map<string, { attempted: boolean; landed: boolean }>();
    for (const session of sessions) {
      const key = dateKey(new Date(session.ended_at));
      const current = sessionByDay.get(key) ?? { attempted: false, landed: false };
      current.attempted = current.attempted || session.attempts_count > 0;
      current.landed = current.landed || session.landed_count > 0;
      sessionByDay.set(key, current);
    }
    const slots: DaySlot[] = [];
    for (let daysAgo = 6; daysAgo >= 0; daysAgo--) {
      const d = new Date(); d.setHours(12, 0, 0, 0); d.setDate(d.getDate() - daysAgo);
      const row = sessionByDay.get(dateKey(d));
      slots.push({ date: dateKey(d), label: d.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase(), status: row?.landed ? "landed" : row?.attempted ? "bailed" : "none" });
    }
    return slots;
  }, [sessions]);

  const momentum = useMemo(() => {
    const top = stats.tricks[0];
    return top ? { trick: top.trick, rate: pct(top.lands, top.entries), entries: top.entries } : null;
  }, [stats.tricks]);

  return (
    <View style={[s.screen, { paddingTop: insets.top + 12, paddingBottom: insets.bottom }]}> 
      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
        <View style={s.header}><Eyebrow color={C.volt}>PTE.FLOW</Eyebrow><Text style={s.title}>Progress you can prove.</Text><Text style={s.sub}>Self-reported consistency and video evidence stay separate. PTE only scores what the footage can actually support.</Text></View>

        <View style={s.metricRow}>
          <View style={s.metric}><Text style={s.metricValue}>{stats.total}</Text><Text style={s.metricLabel}>ATTEMPTS</Text></View>
          <View style={s.metric}><Text style={s.metricValue}>{stats.landed}</Text><Text style={s.metricLabel}>LANDS</Text></View>
          <View style={s.metric}><Text style={s.metricValue}>{pct(stats.landed, stats.total)}</Text><Text style={s.metricLabel}>LAND RATE</Text></View>
        </View>

        <Card accent={C.volt}><Eyebrow color={C.volt}>CONSISTENCY / LAST 7 DAYS</Eyebrow><WeekRow days={week} /><Text style={s.note}>Green = a completed session with a reported land. Pink = attempts without a land. This is session consistency, not a PTE score.</Text></Card>

        <Card>
          <Eyebrow color={C.volt}>VIDEO PTE TREND</Eyebrow>
          {timelineLoading && !ratings.length ? <View style={s.loading}><ActivityIndicator color={C.volt} /><Text style={s.note}>Loading progression evidence…</Text></View> : ratings.length ? <><RatingLine ratings={ratings} /><Text style={s.note}>Plotted from analyzed clip/session PTE results only. No usable evidence means no invented score.</Text></> : <View style={s.empty}><Text style={s.emptyTitle}>No video-rated attempts yet.</Text><Text style={s.note}>Film attempts from Flow. Once a clip supports a rating, the trend appears here.</Text></View>}
          {timelineError ? <Text style={s.apiNote}>Progression sync unavailable right now. Showing on-device history where available.</Text> : null}
        </Card>

        {timeline.length ? <View style={{ gap: 10 }}><Eyebrow>RECENT PROGRESSION</Eyebrow>{timeline.slice(0, 5).map((item) => <View key={item.session_id} style={s.timelineRow}><View style={{ flex: 1, gap: 2 }}><Text style={s.trickName}>{item.focus_trick ?? "Session"}</Text><Text style={s.note}>{shortDate(item.ended_at)}{item.spot ? ` · ${item.spot}` : ""} · {item.clips_count} clips</Text></View><Text style={[s.trickRate, item.best_pte_score == null && { color: C.dim }]}>{item.best_pte_score == null ? "—" : item.best_pte_score.toFixed(1)}</Text></View>)}</View> : null}

        <View style={{ gap: 10 }}><Eyebrow>MOST WORKED TRICKS</Eyebrow>{stats.tricks.length ? stats.tricks.map((row, index) => <View key={row.trick} style={s.trickRow}><Text style={s.rank}>{String(index + 1).padStart(2, "0")}</Text><View style={{ flex: 1 }}><Text style={s.trickName}>{row.trick}</Text><Text style={s.note}>{row.entries} attempts · {row.lands} landed</Text></View><Text style={s.trickRate}>{pct(row.lands, row.entries)}</Text></View>) : <Text style={s.note}>Complete a Flow session and your trick progression will build here.</Text>}</View>

        {momentum ? <Card accent={C.red}><Eyebrow color={C.red}>CURRENT BATTLE CANDIDATE</Eyebrow><Text style={s.focus}>{momentum.trick}</Text><Text style={s.sub}>{momentum.entries} attempts · {momentum.rate} land rate. Your most-worked trick is ready for a focused Battle session.</Text></Card> : null}
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
  apiNote: { fontFamily: F.mono, fontSize: 9, lineHeight: 14, color: C.red, marginTop: 4 },
  loading: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 14 },
  empty: { paddingVertical: 14, gap: 5 },
  emptyTitle: { fontFamily: F.bold, fontSize: 15, color: C.offwhite },
  trickRow: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: C.charcoal2, borderRadius: 12, padding: 14 },
  timelineRow: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: C.charcoal2, borderRadius: 12, padding: 14, borderLeftWidth: 3, borderLeftColor: C.volt },
  rank: { fontFamily: F.mono, color: C.red, fontSize: 11 },
  trickName: { fontFamily: F.bold, color: C.offwhite, fontSize: 15 },
  trickRate: { fontFamily: F.heading, color: C.volt, fontSize: 18 },
  focus: { fontFamily: F.heading, fontSize: 26, color: C.offwhite, marginTop: 4 },
});
