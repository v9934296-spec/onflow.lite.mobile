import React, { useMemo } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppNav } from "../src/components/AppNav";
import { useAccount } from "../src/auth/accountContext";
import { useSkateSession } from "../src/skateSession/skateSessionContext";
import { useSession } from "../src/session";
import { getBestTrickStreak } from "../src/progress";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow } from "../src/ui";

function formatDate(iso?: string | null): string {
  if (!iso) return "None yet";
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? "None yet"
    : date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={s.section}>
      <Text style={s.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

export default function Home() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAccount();
  const { activeSession, hasActiveSession } = useSkateSession();
  const { attempts, log, selectedTrick } = useSession();

  const streak = useMemo(() => getBestTrickStreak(attempts), [attempts]);
  const latestAnalysis = useMemo(
    () => [...log].reverse().find((entry) => entry.analysis.source === "user"),
    [log],
  );
  const bestPte = useMemo(() => {
    const ratings = log
      .map((entry) => entry.analysis.rating)
      .filter((value): value is number => typeof value === "number");
    return ratings.length ? Math.max(...ratings) : null;
  }, [log]);

  const isBattle = activeSession?.notes?.startsWith("[battle]") ?? false;
  const handle = user?.email?.split("@")[0]?.trim();
  const objective =
    latestAnalysis?.analysis.workOn?.trim() ||
    "Complete a filmed attempt to unlock your next coaching objective.";
  const focusName = selectedTrick?.canonicalName ?? activeSession?.focus_trick ?? null;

  return (
    <View style={[s.screen, { paddingTop: insets.top, paddingBottom: insets.bottom }]}> 
      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
        <View style={s.header}>
          <Eyebrow color={C.volt}>ONFLOW</Eyebrow>
          <Text style={s.h1}>Command Center</Text>
          <Text style={s.subtitle}>Your skating now. Your next move. Nothing fake.</Text>
          {handle ? <Text style={s.signedIn}>@{handle}</Text> : null}
        </View>

        {!attempts.length && !log.length && !hasActiveSession ? (
          <Card accent={C.volt}>
            <Eyebrow color={C.volt}>START HERE</Eyebrow>
            <Text style={s.cardHeading}>Build your first real session.</Text>
            <Text style={s.body}>Pick a trick, log attempts, film clips, and let PTE build progression from evidence instead of guesses.</Text>
            <View style={s.cardAction}>
              <Btn label="Start Flow" onPress={() => router.push("/flow" as never)} />
            </View>
          </Card>
        ) : null}

        <Section title="YOUR FOCUS">
          <Card accent={isBattle ? C.red : C.volt}>
            <Eyebrow color={isBattle ? C.red : C.volt}>{isBattle ? "CURRENT BATTLE" : "CURRENT FLOW"}</Eyebrow>
            {focusName ? (
              <>
                <Text style={s.cardHeading}>{focusName}</Text>
                <Text style={s.body}>{isBattle ? "Battle active" : "Session focus"} · {attempts.length} logged entries</Text>
                {streak ? <Text style={s.momentum}>{streak.streak} day momentum</Text> : null}
              </>
            ) : (
              <>
                <Text style={s.cardHeading}>{hasActiveSession ? "Choose the next trick." : "No active Flow."}</Text>
                <Text style={s.body}>FLOW owns sessions and Battle. Start there when you're ready to skate.</Text>
              </>
            )}
            <View style={s.cardAction}>
              <Btn label={hasActiveSession ? "Open Flow" : "Start Flow"} onPress={() => router.push("/flow" as never)} />
            </View>
          </Card>

          <View style={s.objectiveBlock}>
            <Eyebrow color={C.red}>CURRENT OBJECTIVE</Eyebrow>
            <Text style={s.objective}>{objective}</Text>
          </View>
        </Section>

        <Section title="AT A GLANCE">
          <View style={s.statsGrid}>
            <View style={[s.statTile, { borderTopColor: C.volt }]}>
              <Text style={s.statBig}>{log.length}</Text>
              <Text style={s.statCaption}>CLIPS LOGGED</Text>
            </View>
            <View style={[s.statTile, { borderTopColor: C.red }]}>
              <Text style={s.statBig}>{hasActiveSession && isBattle ? "1" : "0"}</Text>
              <Text style={s.statCaption}>ACTIVE BATTLES</Text>
            </View>
            <View style={s.statTile}>
              <Text style={s.statBig}>{bestPte != null ? bestPte.toFixed(1) : "—"}</Text>
              <Text style={s.statCaption}>BEST PTE</Text>
            </View>
          </View>
          <Text style={s.lastActivity}>Last clip activity · {formatDate(log.at(-1)?.loggedAt)}</Text>
        </Section>

        <Section title="UPDATES">
          <View style={s.updateBlock}>
            <View style={s.rowBetween}>
              <Eyebrow>NOTIFICATIONS</Eyebrow>
              <Pressable onPress={() => router.push("/notifications" as never)} hitSlop={12}>
                <Text style={s.link}>SEE ALL</Text>
              </Pressable>
            </View>
            <Text style={s.body}>Session recaps, analysis completion, and progression updates surface here when they exist.</Text>
          </View>
        </Section>

        <Section title="TOOLS">
          <View style={s.toolRow}>
            <View style={s.toolCell}>
              <Btn label="Session History" variant="ghost" onPress={() => router.push("/history" as never)} />
            </View>
            <View style={s.toolCell}>
              <Btn label="Settings" variant="ghost" onPress={() => router.push("/settings" as never)} />
            </View>
          </View>
        </Section>
      </ScrollView>
      <AppNav />
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  content: { paddingHorizontal: 20, paddingTop: 18, paddingBottom: 28, gap: 26 },
  header: { gap: 5, paddingBottom: 4 },
  h1: { fontFamily: F.heading, fontSize: 38, lineHeight: 42, color: C.offwhite },
  subtitle: { fontFamily: F.body, fontSize: 14, lineHeight: 20, color: C.dim },
  signedIn: { fontFamily: F.mono, fontSize: 10, color: C.dim, marginTop: 4 },
  section: { gap: 12 },
  sectionTitle: { fontFamily: F.mono, fontSize: 10, letterSpacing: 1.2, color: C.dim },
  cardHeading: { fontFamily: F.heading, fontSize: 22, lineHeight: 27, color: C.offwhite, marginTop: 5 },
  body: { fontFamily: F.body, fontSize: 14, lineHeight: 21, color: C.dim, marginTop: 5 },
  objectiveBlock: { borderLeftWidth: 3, borderLeftColor: C.red, paddingLeft: 14, paddingVertical: 4 },
  objective: { fontFamily: F.body, fontSize: 16, lineHeight: 23, color: C.offwhite, marginTop: 7 },
  momentum: { fontFamily: F.bold, fontSize: 12, color: C.volt, marginTop: 5 },
  cardAction: { marginTop: 12 },
  statsGrid: { flexDirection: "row", gap: 8 },
  statTile: {
    flex: 1,
    backgroundColor: C.charcoal2,
    borderTopWidth: 2,
    borderTopColor: C.aluminum,
    paddingHorizontal: 11,
    paddingVertical: 14,
  },
  statBig: { fontFamily: F.heading, fontSize: 24, color: C.offwhite },
  statCaption: { fontFamily: F.mono, fontSize: 8, letterSpacing: 0.9, color: C.dim, marginTop: 4 },
  lastActivity: { fontFamily: F.mono, fontSize: 9, color: C.dim },
  updateBlock: { borderTopWidth: 1, borderBottomWidth: 1, borderColor: C.charcoal3, paddingVertical: 14 },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  link: { fontFamily: F.bold, fontSize: 10, letterSpacing: 0.8, color: C.volt },
  toolRow: { flexDirection: "row", gap: 10 },
  toolCell: { flex: 1 },
});