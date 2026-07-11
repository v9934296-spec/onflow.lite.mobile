import React, { useEffect } from "react";
import { View, Text, ScrollView, StyleSheet, Alert, Share, Pressable } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { getBestTrickStreak, getLast7Days, getTrickStreak } from "../src/progress";
import { summarizeLog } from "../src/logSummary";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow, WeekRow, Tag } from "../src/ui";
import { RatingLine, BreakdownBars } from "../src/charts";
import { useSession } from "../src/session";

export default function Log() {
  const router = useRouter();
  const { log, attempts, resetLoop, deleteClip, clearSessionLog } = useSession();
  const insets = useSafeAreaInsets();

  useEffect(() => {
    track("log_viewed");
  }, []);

  const summary = summarizeLog(log);
  const rated = log.filter((e) => e.analysis.rating !== null);
  const ratings = rated.map((e) => e.analysis.rating as number);
  const latest = rated.length > 0 ? rated[rated.length - 1] : null;
  const week = getLast7Days(attempts);
  const bestStreak = getBestTrickStreak(attempts);

  const dateLabel = new Date()
    .toLocaleDateString("en-US", { month: "short", day: "numeric" })
    .toUpperCase();

  const handleExport = async () => {
    const payload = JSON.stringify({ log, attempts }, null, 2);
    await Share.share({ message: payload, title: "OnFlow Lite export" });
    track("log_exported");
  };

  const handleClear = () => {
    Alert.alert("Clear session log?", "This removes all logged clips. Progress streaks are kept.", [
      { text: "Cancel", style: "cancel" },
      { text: "Clear", style: "destructive", onPress: () => clearSessionLog() },
    ]);
  };

  const handleDelete = (id: string, trick: string) => {
    Alert.alert("Delete clip?", trick, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => deleteClip(id) },
    ]);
  };

  const outcomeLabel = (e: (typeof log)[0]) => {
    const o = e.manualLog?.manualOutcome ?? (e.landed === true ? "landed" : e.landed === false ? "missed" : null);
    if (o === "landed") return "landed";
    if (o === "missed") return "missed";
    if (o === "unsure") return "unsure";
    return null;
  };

  return (
    <View style={{ flex: 1, backgroundColor: C.charcoal }}>
      <ScrollView contentContainerStyle={[s.content, { paddingTop: insets.top + 16 }]}>
        <Eyebrow>SESSION LOG · {dateLabel}</Eyebrow>

        {log.length > 0 && (
          <Card>
            <Eyebrow color={C.volt}>SESSION SUMMARY</Eyebrow>
            <Text style={s.summaryLine}>
              <Text style={{ color: C.offwhite }}>{summary.totalAttempts}</Text> attempts ·{" "}
              <Text style={{ color: C.volt }}>{summary.landedPct}%</Text> landed ·{" "}
              <Text style={{ color: C.offwhite }}>{summary.practicedTricks.length}</Text> tricks
            </Text>
            <Text style={s.summarySub}>
              {summary.landedCount} landed · {summary.missedCount} missed · {summary.unsureCount} unsure
            </Text>
            {summary.practicedTricks.length > 0 ? (
              <Text style={s.summarySub}>Practiced: {summary.practicedTricks.join(", ")}</Text>
            ) : null}
            <View style={s.tallyRow}>
              <Tag kind="DETECTED" />
              <Text style={s.tallyText}>{summary.evidenceTally.DETECTED}</Text>
              <Tag kind="ESTIMATE" />
              <Text style={s.tallyText}>{summary.evidenceTally.ESTIMATE}</Text>
              <Tag kind="NO EVIDENCE" />
              <Text style={s.tallyText}>{summary.evidenceTally["NO EVIDENCE"]}</Text>
            </View>
          </Card>
        )}

        {attempts.length > 0 && (
          <Card>
            <Eyebrow color={C.volt}>PROGRESS · LAST 7 DAYS</Eyebrow>
            <WeekRow days={week} />
            {bestStreak ? (
              <Text style={s.streakMeta}>
                Best streak: {bestStreak.trick} · {bestStreak.streak} day
                {bestStreak.streak === 1 ? "" : "s"}
              </Text>
            ) : null}
          </Card>
        )}

        {log.length === 0 ? (
          <View style={s.empty}>
            <Text style={s.emptyTitle}>Nothing logged yet.</Text>
            <Text style={s.emptySub}>Film a clip, log the outcome — your session builds itself.</Text>
          </View>
        ) : (
          <>
            {ratings.length > 0 && (
              <Card>
                <Eyebrow color={C.volt}>P.T.E. · RATING OVER SESSION</Eyebrow>
                <RatingLine ratings={ratings} />
              </Card>
            )}

            {latest?.analysis.breakdown && (
              <Card>
                <Eyebrow color={C.volt}>
                  LAST CLIP ·{" "}
                  {(latest.analysis.trickOnFilm ?? latest.analysis.trickCalled).toUpperCase()}{" "}
                  BREAKDOWN
                </Eyebrow>
                <BreakdownBars items={latest.analysis.breakdown} />
              </Card>
            )}

            {log.map((e, i) => {
              const trick = e.analysis.trickOnFilm ?? e.analysis.trickCalled;
              const trickStreak = getTrickStreak(attempts, trick);
              const o = outcomeLabel(e);
              return (
                <View key={e.id} style={s.logCard}>
                  {e.analysis.rating !== null ? (
                    <Text style={s.logRating}>{e.analysis.rating.toFixed(1)}</Text>
                  ) : o === "landed" ? (
                    <Text style={[s.logRating, { fontSize: 14 }]}>✓</Text>
                  ) : o === "missed" ? (
                    <Text style={[s.logRating, { color: C.red, fontSize: 14 }]}>✗</Text>
                  ) : o === "unsure" ? (
                    <Text style={[s.logRating, { color: C.amber, fontSize: 14 }]}>?</Text>
                  ) : (
                    <Text style={[s.logRating, { color: C.dim, fontSize: 14 }]}>N/R</Text>
                  )}
                  <View style={{ flex: 1, gap: 2 }}>
                    <Text style={s.logTrick}>{trick}</Text>
                    <Text style={s.logMeta}>
                      clip {i + 1} · {e.analysis.source === "sample" ? "sample" : "your footage"} ·{" "}
                      {e.analysis.evidenceClass}
                      {e.manualLog ? ` · ${e.manualLog.attempts} attempt${e.manualLog.attempts === 1 ? "" : "s"}` : ""}
                      {o ? ` · ${o}` : ""}
                      {e.manualLog?.spot ? ` · ${e.manualLog.spot}` : ""}
                      {e.analysis.mismatch ? " · called wrong" : ""}
                      {trickStreak > 0 ? ` · ${trickStreak}d streak` : ""}
                    </Text>
                    {e.manualLog?.notes ? (
                      <Text style={s.logNotes}>{e.manualLog.notes}</Text>
                    ) : null}
                    <Text style={s.engineStamp}>{e.analysis.engineVersion}</Text>
                  </View>
                  <Pressable onPress={() => handleDelete(e.id, trick)} hitSlop={8}>
                    <Text style={s.deleteBtn}>✕</Text>
                  </Pressable>
                </View>
              );
            })}
          </>
        )}
      </ScrollView>

      <View style={[s.footer, { paddingBottom: insets.bottom + 16 }]}>
        <Btn
          label="Film a clip"
          onPress={() => {
            resetLoop();
            router.push("/trick");
          }}
        />
        {log.length > 0 && (
          <>
            <Btn label="Export log" variant="ghost" onPress={handleExport} />
            <Btn label="Clear log" variant="red" onPress={handleClear} />
          </>
        )}
        <Btn label="Home" variant="ghost" onPress={() => router.replace("/")} />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  content: { paddingHorizontal: 24, gap: 14, paddingBottom: 16 },
  empty: { paddingVertical: 60, gap: 10 },
  emptyTitle: { fontFamily: F.heading, fontSize: 24, color: C.offwhite },
  emptySub: { fontFamily: F.body, fontSize: 14, lineHeight: 20, color: C.dim },
  summaryLine: { fontFamily: F.body, fontSize: 15, color: C.dim, marginTop: 4 },
  summarySub: { fontFamily: F.mono, fontSize: 10, color: C.dim, marginTop: 4 },
  tallyRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 10, flexWrap: "wrap" },
  tallyText: { fontFamily: F.mono, fontSize: 10, color: C.dim, marginRight: 8 },
  streakMeta: { fontFamily: F.mono, fontSize: 10, color: C.dim, marginTop: 6 },
  logCard: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    backgroundColor: C.charcoal2,
    borderWidth: 1,
    borderColor: C.aluminum,
    borderRadius: 10,
    padding: 14,
  },
  logRating: { fontFamily: F.heading, fontSize: 20, color: C.volt, minWidth: 44 },
  logTrick: { fontFamily: F.bold, fontSize: 14, color: C.offwhite },
  logMeta: { fontFamily: F.mono, fontSize: 10, color: C.dim },
  logNotes: { fontFamily: F.body, fontSize: 12, color: C.dim, lineHeight: 17 },
  engineStamp: { fontFamily: F.mono, fontSize: 8, color: C.dim },
  deleteBtn: { fontFamily: F.mono, fontSize: 14, color: C.dim, padding: 4 },
  footer: { paddingHorizontal: 24, paddingTop: 10, gap: 10, backgroundColor: C.charcoal },
});
