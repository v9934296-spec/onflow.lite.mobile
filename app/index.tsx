import React, { useMemo } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppNav } from "../src/components/AppNav";
import { useAccount } from "../src/auth/accountContext";
import { useSkateSession } from "../src/skateSession/skateSessionContext";
import { useSession } from "../src/session";
import { getBestTrickStreak, getLast7Days } from "../src/progress";
import { C, F } from "../src/theme";
import { Card, Eyebrow, WeekRow } from "../src/ui";

export default function Home() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAccount();
  const { activeSession, hasActiveSession } = useSkateSession();
  const { attempts, log, selectedTrick } = useSession();

  const week = useMemo(() => getLast7Days(attempts), [attempts]);
  const streak = useMemo(() => getBestTrickStreak(attempts), [attempts]);
  const latestAnalysis = useMemo(() => [...log].reverse().find((entry) => entry.analysis.source === "user"), [log]);
  const isBattle = activeSession?.notes?.startsWith("[battle]") ?? false;

  return (
    <View style={[s.screen, { paddingTop: insets.top + 12, paddingBottom: insets.bottom }]}> 
      <View style={s.content}>
        <View style={s.topline}>
          <Eyebrow><Text style={{ color: C.red }}>■ </Text>ONFLOW</Eyebrow>
          <Pressable onPress={() => router.push("/settings" as never)} hitSlop={12}>
            <Text style={s.settings}>SETTINGS</Text>
          </Pressable>
        </View>

        <View style={s.hero}>
          <Text style={s.h1}>Film it.{"\n"}<Text style={{ color: C.red }}>Get it straight.</Text></Text>
          <Text style={s.sub}>Track the work. Film the evidence. Keep progression honest.</Text>
          {user?.email ? <Text style={s.account}>{user.email}</Text> : null}
        </View>

        <Pressable onPress={() => router.replace("/flow" as never)} style={({ pressed }) => [s.primary, pressed && { opacity: 0.78 }]}>
          <View>
            <Eyebrow color={hasActiveSession ? (isBattle ? C.red : C.volt) : C.charcoal}> {hasActiveSession ? (isBattle ? "BATTLE LIVE" : "SESSION LIVE") : "READY WHEN YOU ARE"}</Eyebrow>
            <Text style={s.primaryTitle}>{hasActiveSession ? (selectedTrick?.canonicalName ?? "Continue skating") : "Start skating"}</Text>
          </View>
          <Text style={s.arrow}>→</Text>
        </Pressable>

        <View style={s.grid}>
          <Pressable onPress={() => router.replace("/pte" as never)} style={s.tile}>
            <Eyebrow color={C.volt}>PTE.FLOW</Eyebrow>
            <Text style={s.tileValue}>{attempts.length}</Text>
            <Text style={s.tileLabel}>progress logs</Text>
          </Pressable>
          <Pressable onPress={() => router.push("/history" as never)} style={s.tile}>
            <Eyebrow color={C.red}>HISTORY</Eyebrow>
            <Text style={s.tileValue}>{log.length}</Text>
            <Text style={s.tileLabel}>saved clips</Text>
          </Pressable>
        </View>

        {attempts.length > 0 ? (
          <Card>
            <View style={s.cardHeader}><Eyebrow color={C.volt}>LAST 7 DAYS</Eyebrow>{streak ? <Text style={s.streak}>{streak.streak} DAY STREAK</Text> : null}</View>
            <WeekRow days={week} />
            {streak ? <Text style={s.cardCopy}>Momentum: {streak.trick}</Text> : null}
          </Card>
        ) : (
          <Card accent={C.volt}>
            <Eyebrow color={C.volt}>FIRST SESSION</Eyebrow>
            <Text style={s.cardTitle}>Build the record.</Text>
            <Text style={s.cardCopy}>Start in Flow, choose a trick, log lands and misses. Film only when you want technique evidence.</Text>
          </Card>
        )}

        {latestAnalysis ? (
          <Card accent={latestAnalysis.analysis.abstained ? C.red : C.volt}>
            <Eyebrow color={latestAnalysis.analysis.abstained ? C.red : C.volt}>LATEST AI READ</Eyebrow>
            <Text style={s.cardTitle}>{latestAnalysis.analysis.trickCalled}</Text>
            <Text style={s.cardCopy}>{latestAnalysis.analysis.verdict}</Text>
          </Card>
        ) : null}
      </View>
      <AppNav />
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  content: { flex: 1, paddingHorizontal: 24, paddingTop: 12, gap: 16 },
  topline: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  settings: { fontFamily: F.mono, fontSize: 9, letterSpacing: 1, color: C.dim },
  hero: { gap: 8, paddingTop: 8 },
  h1: { fontFamily: F.heading, fontSize: 40, lineHeight: 43, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 14, lineHeight: 21, color: C.dim, maxWidth: 340 },
  account: { fontFamily: F.mono, fontSize: 9, color: C.dim },
  primary: { minHeight: 92, borderRadius: 16, paddingHorizontal: 18, paddingVertical: 16, backgroundColor: C.volt, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  primaryTitle: { fontFamily: F.heading, fontSize: 25, color: C.charcoal, marginTop: 3 },
  arrow: { fontFamily: F.heading, fontSize: 30, color: C.charcoal },
  grid: { flexDirection: "row", gap: 10 },
  tile: { flex: 1, minHeight: 96, backgroundColor: C.charcoal2, borderRadius: 14, padding: 14 },
  tileValue: { fontFamily: F.heading, fontSize: 28, color: C.offwhite, marginTop: 8 },
  tileLabel: { fontFamily: F.body, fontSize: 11, color: C.dim },
  cardHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  streak: { fontFamily: F.mono, fontSize: 9, color: C.red },
  cardTitle: { fontFamily: F.bold, fontSize: 17, color: C.offwhite, marginTop: 4 },
  cardCopy: { fontFamily: F.body, fontSize: 12, lineHeight: 18, color: C.dim, marginTop: 4 },
});
