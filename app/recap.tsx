import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import Svg, { Circle } from "react-native-svg";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { loadLastRecapSessionId } from "../src/activeSessionStore";
import { useAccount } from "../src/auth/accountContext";
import { loadCompletedSessionRecap } from "../src/sessionRecap/completedSessionStore";
import { C, F, withOpacity } from "../src/theme";
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

function landedRate(recap: SessionRecap): number | null {
  if (recap.attempts_count === 0) return null;
  if (recap.landed_rate != null) return recap.landed_rate;
  return recap.landed_count / recap.attempts_count;
}

function rateColor(rate: number | null): string {
  if (rate == null) return C.charcoal5;
  return rate >= 0.5 ? C.volt : C.red;
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
        <Text style={s.sub}>Building recap…</Text>
      </View>
    );
  }

  if (!resolvedSessionId || error || !recap) {
    return (
      <View style={[s.screen, s.centered, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
        <Eyebrow color={C.red}>NO RECAP</Eyebrow>
        <Text style={s.title}>Nothing to show yet.</Text>
        <Text style={s.sub}>{error ?? "Finish a session to see your results here."}</Text>
        <Btn label="Back home" onPress={() => router.replace("/" as never)} />
      </View>
    );
  }

  const rate = landedRate(recap);
  const accent = rateColor(rate);
  const gaugeSize = 168;
  const stroke = 12;
  const radius = (gaugeSize - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = rate == null ? 0 : Math.max(0, Math.min(1, rate));
  const dash = circumference * progress;

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <ScrollView contentContainerStyle={{ gap: 18, paddingBottom: 20 }} showsVerticalScrollIndicator={false}>
        <View style={{ gap: 6 }}>
          <Eyebrow color={C.volt}>SESSION COMPLETE</Eyebrow>
          <Text style={s.title}>{recap.focus_trick ?? "Good work."}</Text>
          <Text style={s.subLeft}>{recap.spot_label ?? "Session recap"}</Text>
        </View>

        <View style={s.gaugeWrap}>
          <Svg width={gaugeSize} height={gaugeSize}>
            <Circle
              cx={gaugeSize / 2}
              cy={gaugeSize / 2}
              r={radius}
              stroke={C.charcoal4}
              strokeWidth={stroke}
              fill="none"
            />
            <Circle
              cx={gaugeSize / 2}
              cy={gaugeSize / 2}
              r={radius}
              stroke={accent}
              strokeWidth={stroke}
              fill="none"
              strokeDasharray={`${dash} ${circumference}`}
              strokeLinecap="round"
              transform={`rotate(-90 ${gaugeSize / 2} ${gaugeSize / 2})`}
            />
          </Svg>
          <View style={s.gaugeCenter}>
            <Text style={[s.heroValue, { color: accent }]}>{landedPct(recap)}</Text>
            <Text style={[s.heroLabel, { color: accent }]}>LAND RATE</Text>
          </View>
        </View>
        <Text style={s.heroMeta}>
          {recap.landed_count} landed · {recap.missed_count} missed · {recap.attempts_count} attempts
        </Text>

        <View style={s.metricRow}>
          <View style={s.metric}>
            <Text style={s.metricValue}>{recap.attempts_count}</Text>
            <Text style={s.metricLabel}>ATTEMPTS</Text>
          </View>
          <View style={[s.metric, { borderColor: withOpacity(C.volt, 0.45) }]}>
            <Text style={[s.metricValue, { color: C.volt }]}>{recap.landed_count}</Text>
            <Text style={s.metricLabel}>LANDED</Text>
          </View>
          <View style={s.metric}>
            <Text style={s.metricValue}>{formatDuration(recap.duration_seconds)}</Text>
            <Text style={s.metricLabel}>TIME</Text>
          </View>
        </View>

        {recap.trick_breakdown.length > 0 ? (
          <View style={{ gap: 10 }}>
            <Eyebrow>WHAT YOU WORKED</Eyebrow>
            {recap.trick_breakdown.map((row) => {
              const total = row.landed + row.missed;
              const rowRate = total > 0 ? row.landed / total : null;
              const rowAccent = rateColor(rowRate);
              return (
                <View key={row.canonicalName} style={s.breakdownRow}>
                  <View style={{ flex: 1, gap: 8 }}>
                    <View style={s.breakdownTop}>
                      <View style={{ flex: 1 }}>
                        <Text style={s.breakdownTrick}>{row.canonicalName}</Text>
                        <Text style={s.breakdownMeta}>
                          {row.landed} landed · {row.missed} missed
                        </Text>
                      </View>
                      <Text style={[s.breakdownRate, { color: rowAccent }]}>
                        {rowRate != null ? `${Math.round(rowRate * 100)}%` : "—"}
                      </Text>
                    </View>
                    <View style={s.splitTrack}>
                      {total > 0 ? (
                        <>
                          <View style={[s.splitLanded, { flex: Math.max(row.landed, 0.001) }]} />
                          <View style={[s.splitMissed, { flex: Math.max(row.missed, 0.001) }]} />
                        </>
                      ) : (
                        <View style={s.splitEmpty} />
                      )}
                    </View>
                  </View>
                </View>
              );
            })}
          </View>
        ) : (
          <Card accent={C.red}>
            <Eyebrow color={C.red}>NO ATTEMPTS</Eyebrow>
            <Text style={s.cardCopy}>You ended this session without logging attempts. No numbers were invented.</Text>
          </Card>
        )}

        <Card accent={C.volt}>
          <Eyebrow color={C.volt}>NEXT</Eyebrow>
          <Text style={s.cardTitle}>Keep the progression record moving.</Text>
          <Text style={s.cardCopy}>
            PTE.Flow separates self-reported consistency from video evidence so you can see what is improving without fake precision.
          </Text>
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
  gaugeWrap: {
    alignSelf: "center",
    width: 168,
    height: 168,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: C.volt,
    shadowOpacity: 0.25,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 0 },
  },
  gaugeCenter: {
    position: "absolute",
    alignItems: "center",
    justifyContent: "center",
  },
  heroValue: { fontFamily: F.heading, fontSize: 42, lineHeight: 46, color: C.volt },
  heroLabel: { fontFamily: F.mono, fontSize: 10, letterSpacing: 1.2, color: C.volt },
  heroMeta: {
    fontFamily: F.body,
    fontSize: 12,
    color: C.dim,
    textAlign: "center",
    marginTop: -4,
  },
  metricRow: { flexDirection: "row", gap: 8 },
  metric: {
    flex: 1,
    backgroundColor: C.charcoal,
    borderRadius: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.charcoal4,
    padding: 13,
  },
  metricValue: { fontFamily: F.heading, fontSize: 26, color: C.offwhite },
  metricLabel: { fontFamily: F.mono, fontSize: 8, letterSpacing: 0.7, color: C.dim, marginTop: 3 },
  breakdownRow: {
    backgroundColor: C.charcoal,
    borderRadius: 12,
    padding: 14,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.charcoal4,
  },
  breakdownTop: { flexDirection: "row", alignItems: "center" },
  breakdownTrick: { fontFamily: F.bold, fontSize: 15, color: C.offwhite },
  breakdownMeta: { fontFamily: F.body, fontSize: 12, color: C.dim, marginTop: 2 },
  breakdownRate: { fontFamily: F.heading, fontSize: 22, color: C.volt },
  splitTrack: {
    height: 8,
    borderRadius: 4,
    overflow: "hidden",
    flexDirection: "row",
    backgroundColor: C.charcoal4,
  },
  splitLanded: { backgroundColor: C.volt },
  splitMissed: { backgroundColor: C.red },
  splitEmpty: { flex: 1, backgroundColor: C.charcoal4 },
  cardTitle: { fontFamily: F.bold, fontSize: 16, color: C.offwhite, marginTop: 4 },
  cardCopy: { fontFamily: F.body, fontSize: 12, lineHeight: 18, color: C.dim, marginTop: 4 },
});
