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
  const { attempts, log, selectedTrick, pendingClipJobId } = useSession();

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
  const analysisPending = Boolean(pendingClipJobId);

  return (
    <View style={[s.screen, { paddingTop: insets.top, paddingBottom: insets.bottom }]}> 
      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
        <View style={s.header}>
          <Text style={s.h1}>OnFlow</Text>
          <Text style={s.subtitle}>Command Center</Text>
          {handle ? <Text style={s.signedIn}>Signed in as {handle}</Text> : null}
        </View>

        {analysisPending ? (
          <Card accent={C.amber}>
            <Eyebrow color={C.amber}>ANALYSIS RECOVERED</Eyebrow>
            <Text style={s.cardHeading}>Your unfinished analysis is still saved.</Text>
            <Text style={s.body}>
              OnFlow restored the job after the app closed. Resume checking the server instead of uploading the clip again.
            </Text>
            <View style={s.cardAction}>
              <Btn label="Resume analysis" onPress={() => router.push("/analyzing" as never)} />
            </View>
          </Card>
        ) : null}

        {!attempts.length && !log.length && !hasActiveSession && !analysisPending ? (
          <Card accent={C.volt}>
            <Eyebrow color={C.dim}>WELCOME</Eyebrow>
            <Text style={s.cardHeading}>Welcome to OnFlow</Text>
            <Text style={s.body}>
              Film skate clips, get honest coaching, and track progression over time. Start with your first session.
            </Text>
            <View style={s.cardAction}>
              <Btn label="Start Session" onPress={() => router.push("/flow" as never)} />
            </View>
          </Card>
        ) : null}

        <Section title="YOUR FOCUS">
          <Card accent={isBattle ? C.red : C.volt}>
            <Eyebrow color={C.dim}>CURRENT BATTLE</Eyebrow>
            {focusName ? (
              <>
                <Text style={s.cardHeading}>{focusName}</Text>
                <Text style={s.body}>
                  {isBattle ? "Battle active" : "Current focus"} · {attempts.length} logged entries
                </Text>
                {streak ? <Text style={s.momentum}>{streak.streak} day momentum</Text> : null}
              </>
            ) : (
              <Text style={s.body}>Pick a trick and start skating to see your focus here.</Text>
            )}
          </Card>

          <Card accent={C.red}>
            <Eyebrow color={C.dim}>CURRENT OBJECTIVE</Eyebrow>
            <Text style={s.objective}>{objective}</Text>
          </Card>
        </Section>

        <Section title="AT A GLANCE">
          <Card>
            <Eyebrow color={C.dim}>QUICK PROGRESS SUMMARY</Eyebrow>
            <View style={s.statsList}>
              <View style={s.statRow}>
                <Text style={s.statLabel}>Sessions logged</Text>
                <Text style={s.statValue}>{log.length || "None yet"}</Text>
              </View>
              <View style={s.statRow}>
                <Text style={s.statLabel}>Active battles</Text>
                <Text style={s.statValue}>{hasActiveSession && isBattle ? "1" : "0"}</Text>
              </View>
              <View style={s.statRow}>
                <Text style={s.statLabel}>Last activity</Text>
                <Text style={s.statValue}>{formatDate(log.at(-1)?.loggedAt)}</Text>
              </View>
              <View style={s.statRow}>
                <Text style={s.statLabel}>Recent best PTE</Text>
                <Text style={s.statValue}>{bestPte != null ? bestPte.toFixed(1) : "None yet"}</Text>
              </View>
            </View>
          </Card>
        </Section>

        <Section title="UPDATES">
          <Card>
            <View style={s.rowBetween}>
              <Eyebrow color={C.dim}>NOTIFICATIONS</Eyebrow>
              <Pressable onPress={() => router.push("/notifications" as never)} hitSlop={12}>
                <Text style={s.link}>See all</Text>
              </Pressable>
            </View>
            <Text style={s.body}>No notifications yet. Session recaps and progression updates will appear here.</Text>
          </Card>
        </Section>

        <Section title="GO DEEPER">
          <Card>
            <Eyebrow color={C.dim}>QUICK LINKS</Eyebrow>
            <View style={s.quickLinks}>
              <Btn label="Open Feed" variant="ghost" onPress={() => router.push("/feed" as never)} />
              <Btn label="Open PTE.Flow" variant="ghost" onPress={() => router.push("/pte" as never)} />
              <Btn label="Session History" variant="ghost" onPress={() => router.push("/history" as never)} />
              <Btn
                label={hasActiveSession ? "Continue Session" : "Start Session"}
                onPress={() => router.push("/flow" as never)}
              />
            </View>
          </Card>
        </Section>
      </ScrollView>
      <AppNav />
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  content: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 28, gap: 26 },
  header: { paddingBottom: 4 },
  h1: { fontFamily: F.heading, fontSize: 38, lineHeight: 42, color: C.offwhite },
  subtitle: { fontFamily: F.body, fontSize: 14, color: C.dim, marginTop: 2 },
  signedIn: { fontFamily: F.body, fontSize: 12, color: C.dim, marginTop: 8 },
  section: { gap: 12 },
  sectionTitle: { fontFamily: F.bold, fontSize: 12, letterSpacing: 0.7, color: C.dim },
  cardHeading: { fontFamily: F.heading, fontSize: 22, lineHeight: 27, color: C.offwhite, marginTop: 6 },
  body: { fontFamily: F.body, fontSize: 14, lineHeight: 21, color: C.dim, marginTop: 6 },
  objective: { fontFamily: F.body, fontSize: 16, lineHeight: 23, color: C.offwhite, marginTop: 8 },
  momentum: { fontFamily: F.bold, fontSize: 12, color: C.volt, marginTop: 5 },
  cardAction: { marginTop: 14 },
  statsList: { gap: 12, marginTop: 12 },
  statRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 16 },
  statLabel: { flex: 1, fontFamily: F.body, fontSize: 13, color: C.dim },
  statValue: { fontFamily: F.bold, fontSize: 13, color: C.offwhite, textAlign: "right" },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  link: { fontFamily: F.bold, fontSize: 12, color: C.volt },
  quickLinks: { gap: 10, marginTop: 12 },
});
