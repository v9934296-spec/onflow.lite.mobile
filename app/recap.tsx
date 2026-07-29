import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { loadLastRecapSessionId } from "../src/activeSessionStore";
import { loadCompletedSessionRecap } from "../src/sessionRecap/completedSessionStore";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow } from "../src/ui";
import type { SessionRecap } from "../src/types/sessionRecap";

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  if (seconds < 60) return "<1m";
  return `${Math.round(seconds / 60)}m`;
}

function landedPct(recap: SessionRecap): string {
  if (recap.attempts_count === 0) return "—";
  if (recap.landed_rate != null) return `${Math.round(recap.landed_rate * 100)}%`;
  return `${Math.round((recap.landed_count / recap.attempts_count) * 100)}%`;
}

export default function RecapScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ sessionId?: string }>();
  const [resolvedSessionId, setResolvedSessionId] = useState<string | null>(typeof params.sessionId === "string" && params.sessionId.trim() ? params.sessionId : null);
  const [resolving, setResolving] = useState(!resolvedSessionId);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recap, setRecap] = useState<SessionRecap | null>(null);

  useEffect(() => {
    if (resolvedSessionId) return;
    let cancelled = false;
    void (async () => {
      const sid = await loadLastRecapSessionId().catch(() => null);
      if (!cancelled) { setResolvedSessionId(sid); setResolving(false); }
    })();
    return () => { cancelled = true; };
  }, [resolvedSessionId]);

  useEffect(() => {
    if (!resolvedSessionId) { setLoading(false); setRecap(null); return; }
    let cancelled = false;
    setLoading(true);
    setError(null);
    void (async () => {
      const result = await loadCompletedSessionRecap(resolvedSessionId);
      if (cancelled) return;
      if (result.loadError) setError(result.loadError);
      if (!result.data) { setRecap(null); setError("Recap not found for this session."); }
      else { setRecap(result.data); track("session_recap_viewed", { session_id: resolvedSessionId }); }
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [resolvedSessionId]);

  if (resolving || loading) {
    return <View style={[s.screen, s.centered, { paddingTop: insets.top + 16 }]}><ActivityIndicator color={C.volt} /><Text style={s.sub}>Building recap…</Text></View>;
  }

  if (!resolvedSessionId || error || !recap) {
    return (
      <View style={[s.screen, s.centered, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
        <Eyebrow color={C.red}>NO RECAP</Eyebrow><Text style={s.title}>Nothing to show yet.</Text><Text style={s.sub}>{error ?? "Finish a session to see your results here."}</Text><Btn label="Back home" onPress={() => router.replace("/" as never)} />
      </View>
    );
  }

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <ScrollView contentContainerStyle={{ gap: 18, paddingBottom: 20 }} showsVerticalScrollIndicator={false}>
        <View style={{ gap: 6 }}>
          <Eyebrow color={C.volt}>SESSION COMPLETE</Eyebrow>
          <Text style={s.title}>{recap.focus_trick ?? "Good work."}</Text>
          <Text style={s.subLeft}>{recap.spot_label ?? "Session recap"}</Text>
        </View>

        <View style={s.heroMetric}>
          <Text style={s.heroValue}>{landedPct(recap)}</Text>
          <Text style={s.heroLabel}>LAND RATE</Text>
          <Text style={s.heroMeta}>{recap.landed_count} landed · {recap.missed_count} missed · {recap.attempts_count} attempts</Text>
        </View>

        <View style={s.metricRow}>
          <View style={s.metric}><Text style={s.metricValue}>{recap.attempts_count}</Text><Text style={s.metricLabel}>ATTEMPTS</Text></View>
          <View style={s.metric}><Text style={s.metricValue}>{recap.landed_count}</Text><Text style={s.metricLabel}>LANDED</Text></View>
          <View style={s.metric}><Text style={s.metricValue}>{formatDuration(recap.duration_seconds)}</Text><Text style={s.metricLabel}>TIME</Text></View>
        </View>

        {recap.trick_breakdown.length > 0 ? (
          <View style={{ gap: 10 }}>
            <Eyebrow>WHAT YOU WORKED</Eyebrow>
            {recap.trick_breakdown.map((row) => (
              <View key={row.canonicalName} style={s.breakdownRow}>
                <View style={{ flex: 1 }}><Text style={s.breakdownTrick}>{row.canonicalName}</Text><Text style={s.breakdownMeta}>{row.landed} landed · {row.missed} missed</Text></View>
                <Text style={s.breakdownRate}>{row.landed + row.missed > 0 ? `${Math.round((row.landed / (row.landed + row.missed)) * 100)}%` : "—"}</Text>
              </View>
            ))}
          </View>
        ) : <Card accent={C.red}><Eyebrow color={C.red}>NO ATTEMPTS</Eyebrow><Text style={s.cardCopy}>You ended this session without logging attempts. No numbers were invented.</Text></Card>}

        <Card accent={C.volt}>
          <Eyebrow color={C.volt}>NEXT</Eyebrow>
          <Text style={s.cardTitle}>Keep the progression record moving.</Text>
          <Text style={s.cardCopy}>PTE.Flow separates self-reported consistency from video evidence so you can see what is improving without fake precision.</Text>
        </Card>
      </ScrollView>

      <View style={{ gap: 10 }}>
        <Btn label="Open PTE.Flow" onPress={() => router.replace("/pte" as never)} />
        <Btn label="Back home" variant="ghost" onPress={() => router.replace("/" as never)} />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24, gap: 12 },
  centered: { alignItems: "center", justifyContent: "center", gap: 12 },
  title: { fontFamily: F.heading, fontSize: 32, lineHeight: 36, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 14, lineHeight: 20, color: C.dim, textAlign: "center" },
  subLeft: { fontFamily: F.body, fontSize: 13, color: C.dim },
  heroMetric: { borderLeftWidth: 5, borderLeftColor: C.volt, paddingLeft: 16, paddingVertical: 8 },
  heroValue: { fontFamily: F.heading, fontSize: 54, lineHeight: 58, color: C.offwhite },
  heroLabel: { fontFamily: F.mono, fontSize: 10, letterSpacing: 1.2, color: C.volt },
  heroMeta: { fontFamily: F.body, fontSize: 12, color: C.dim, marginTop: 5 },
  metricRow: { flexDirection: "row", gap: 8 },
  metric: { flex: 1, backgroundColor: C.charcoal2, borderRadius: 12, padding: 13 },
  metricValue: { fontFamily: F.heading, fontSize: 22, color: C.offwhite },
  metricLabel: { fontFamily: F.mono, fontSize: 8, letterSpacing: 0.7, color: C.dim, marginTop: 3 },
  breakdownRow: { flexDirection: "row", alignItems: "center", backgroundColor: C.charcoal2, borderRadius: 12, padding: 14, borderLeftWidth: 3, borderLeftColor: C.volt },
  breakdownTrick: { fontFamily: F.bold, fontSize: 15, color: C.offwhite },
  breakdownMeta: { fontFamily: F.body, fontSize: 12, color: C.dim, marginTop: 2 },
  breakdownRate: { fontFamily: F.heading, fontSize: 19, color: C.volt },
  cardTitle: { fontFamily: F.bold, fontSize: 16, color: C.offwhite, marginTop: 4 },
  cardCopy: { fontFamily: F.body, fontSize: 12, lineHeight: 18, color: C.dim, marginTop: 4 },
});
