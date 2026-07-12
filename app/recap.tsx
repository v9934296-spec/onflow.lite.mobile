import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { loadLastRecapSessionId } from "../src/activeSessionStore";
import { track } from "../src/analytics";
import { useAccount } from "../src/auth/accountContext";
import { loadCompletedSessionRecap } from "../src/sessionRecap/completedSessionStore";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow } from "../src/ui";
import type { SessionRecap } from "../src/types/sessionRecap";

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "Not enough data yet";
  if (seconds < 60) return "Under a minute";
  const minutes = Math.round(seconds / 60);
  return `${minutes} ${minutes === 1 ? "minute" : "minutes"}`;
}

function formatLandedRate(recap: SessionRecap): string {
  if (recap.attempts_count === 0) return "No attempts logged";
  const pct = recap.landed_rate != null ? ` (${Math.round(recap.landed_rate * 100)}%)` : "";
  return `${recap.landed_count}/${recap.attempts_count}${pct}`;
}

export default function RecapScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ sessionId?: string }>();
  const { user } = useAccount();
  const userId = user?.user_id ?? null;

  const [resolvedSessionId, setResolvedSessionId] = useState<string | null>(
    typeof params.sessionId === "string" && params.sessionId.trim() ? params.sessionId : null,
  );
  const [resolving, setResolving] = useState(!resolvedSessionId);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recap, setRecap] = useState<SessionRecap | null>(null);

  useEffect(() => {
    if (resolvedSessionId) return;
    if (!userId) {
      setResolving(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      const sid = await loadLastRecapSessionId(userId).catch(() => null);
      if (!cancelled) {
        setResolvedSessionId(sid);
        setResolving(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [resolvedSessionId, userId]);

  useEffect(() => {
    if (!userId || !resolvedSessionId) {
      setLoading(false);
      setRecap(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    void (async () => {
      const result = await loadCompletedSessionRecap(userId, resolvedSessionId);
      if (cancelled) return;
      if (result.loadError) setError(result.loadError);
      if (!result.data) {
        setRecap(null);
        setError("Recap not found for this session.");
      } else {
        setRecap(result.data);
        track("session_recap_viewed", { session_id: resolvedSessionId });
      }
      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [resolvedSessionId, userId]);

  if (resolving || loading) {
    return (
      <View style={[s.screen, s.centered, { paddingTop: insets.top + 16 }]}>
        <ActivityIndicator color={C.volt} />
        <Text style={s.sub}>Loading recap…</Text>
      </View>
    );
  }

  if (!resolvedSessionId || error || !recap) {
    return (
      <View style={[s.screen, s.centered, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
        <Text style={s.title}>No recap yet</Text>
        <Text style={s.sub}>{error ?? "Finish a session to see your results here."}</Text>
        <Btn label="Back home" onPress={() => router.replace("/")} />
      </View>
    );
  }

  const metrics = [
    { label: "Attempts", value: String(recap.attempts_count) },
    { label: "Landed", value: formatLandedRate(recap) },
    { label: "Missed", value: String(recap.missed_count) },
    { label: "Duration", value: formatDuration(recap.duration_seconds) },
  ];

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <ScrollView contentContainerStyle={{ gap: 16, paddingBottom: 16 }}>
        <View style={{ gap: 6 }}>
          <Eyebrow color={C.volt}>SESSION COMPLETE</Eyebrow>
          <Text style={s.title}>Recap</Text>
          <Text style={s.sub}>Self-reported attempts from this session.</Text>
        </View>

        {recap.spot_label ? (
          <View style={{ gap: 4 }}>
            <Eyebrow>SPOT</Eyebrow>
            <Text style={s.spot}>{recap.spot_label}</Text>
          </View>
        ) : null}

        {recap.focus_trick ? (
          <View style={{ gap: 4 }}>
            <Eyebrow>FOCUS</Eyebrow>
            <Text style={s.focus}>{recap.focus_trick}</Text>
          </View>
        ) : null}

        <View style={s.metricsGrid}>
          {metrics.map((m) => (
            <Card key={m.label}>
              <Eyebrow>{m.label.toUpperCase()}</Eyebrow>
              <Text style={s.metricValue}>{m.value}</Text>
            </Card>
          ))}
        </View>

        {recap.trick_breakdown.length > 0 ? (
          <View style={{ gap: 8 }}>
            <Eyebrow>TRICK BREAKDOWN</Eyebrow>
            {recap.trick_breakdown.map((row) => (
              <View key={row.canonicalName} style={s.breakdownRow}>
                <Text style={s.breakdownTrick}>{row.canonicalName}</Text>
                <Text style={s.breakdownMeta}>
                  {row.landed} landed · {row.missed} missed
                </Text>
              </View>
            ))}
          </View>
        ) : (
          <Text style={s.sub}>No attempts were logged in this session.</Text>
        )}
      </ScrollView>

      <Btn label="Back home" onPress={() => router.replace("/")} />
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24, gap: 12 },
  centered: { alignItems: "center", justifyContent: "center", gap: 12 },
  title: { fontFamily: F.heading, fontSize: 28, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 14, lineHeight: 20, color: C.dim, textAlign: "center" },
  spot: { fontFamily: F.heading, fontSize: 22, color: C.offwhite },
  focus: { fontFamily: F.bold, fontSize: 16, color: C.offwhite },
  metricsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  metricValue: { fontFamily: F.bold, fontSize: 15, color: C.offwhite, marginTop: 4 },
  breakdownRow: {
    borderLeftWidth: 3,
    borderLeftColor: C.volt,
    paddingLeft: 10,
    gap: 2,
  },
  breakdownTrick: { fontFamily: F.bold, fontSize: 14, color: C.offwhite },
  breakdownMeta: { fontFamily: F.body, fontSize: 12, color: C.dim },
});
