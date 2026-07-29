import React, { useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppNav } from "../src/components/AppNav";
import { createSkateSession } from "../src/api/sessionApi";
import { saveActiveSessionId } from "../src/activeSessionStore";
import { useSkateSession } from "../src/skateSession/skateSessionContext";
import { useSessionAttempts } from "../src/sessionAttempts/useSessionAttempts";
import { useSession } from "../src/session";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow } from "../src/ui";

export default function FlowScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { selectedTrick, resetLoop } = useSession();
  const {
    activeSession,
    hasActiveSession,
    hydrateState,
    isCreating,
    createError,
    startSession,
    refreshActiveSession,
    endSession,
    isEnding,
    endError,
  } = useSkateSession();
  const { counts, isSubmitting, submitError, logAttempt } = useSessionAttempts(activeSession?.id ?? null);
  const [startingBattle, setStartingBattle] = useState(false);

  const isBattle = activeSession?.notes?.startsWith("[battle]") ?? false;
  const busy = isCreating || startingBattle || isSubmitting || isEnding || hydrateState === "loading";

  async function openSession(mode: "session" | "battle") {
    if (busy) return;
    if (hasActiveSession) {
      router.push("/trick?returnTo=/flow" as never);
      return;
    }
    resetLoop();
    if (mode === "session") {
      const ok = await startSession();
      if (ok) router.push("/trick?returnTo=/flow" as never);
      return;
    }

    setStartingBattle(true);
    try {
      const result = await createSkateSession({ notes: "[battle] Single-trick battle session" });
      if (!result.ok) {
        Alert.alert("Could not start battle", result.error.message);
        return;
      }
      await saveActiveSessionId(result.data.id);
      await refreshActiveSession();
      router.push("/trick?returnTo=/flow" as never);
    } finally {
      setStartingBattle(false);
    }
  }

  async function finishSession() {
    if (!hasActiveSession || busy) return;
    const finish = async () => {
      const result = await endSession();
      if (!result.ok) return;
      resetLoop();
      router.replace(`/recap?sessionId=${encodeURIComponent(result.recap.session_id)}` as never);
    };
    if (counts.total === 0) {
      Alert.alert("End empty session?", "You haven't logged any attempts yet.", [
        { text: "Keep skating", style: "cancel" },
        { text: "End session", style: "destructive", onPress: () => void finish() },
      ]);
      return;
    }
    await finish();
  }

  return (
    <View style={[s.screen, { paddingTop: insets.top, paddingBottom: insets.bottom }]}> 
      <ScrollView contentContainerStyle={s.content} showsVerticalScrollIndicator={false}>
        <View style={s.header}>
          <Text style={s.title}>Flow</Text>
          <Text style={s.subtitle}>Your session loop</Text>
        </View>

        {!hasActiveSession ? (
          <Card>
            <Text style={s.welcome}>Sessions are how you film, upload, and build progression.</Text>
            <Text style={s.body}>Start a session, add attempts and clips as you skate, then end it for a recap.</Text>
          </Card>
        ) : null}

        <Card accent={isBattle ? C.red : C.volt}>
          <Eyebrow color={C.dim}>SESSION</Eyebrow>
          {hydrateState === "loading" ? (
            <View style={s.loading}><ActivityIndicator color={C.volt} /><Text style={s.body}>Loading session…</Text></View>
          ) : hasActiveSession ? (
            <>
              <Text style={s.cardHeading}>{isBattle ? "Battle in progress" : "Session in progress"}</Text>
              <Text style={s.body}>{activeSession?.spot_label ?? "No spot set"} · {counts.total} attempts</Text>
              <View style={s.actions}><Btn label="Continue Session" onPress={() => router.push("/trick?returnTo=/flow" as never)} /></View>
            </>
          ) : (
            <>
              <Text style={s.body}>No active session yet. Start one and get skating.</Text>
              <View style={s.actions}><Btn label="Start Session" onPress={() => void openSession("session")} /></View>
            </>
          )}
        </Card>

        {!hasActiveSession ? (
          <Card accent={C.red}>
            <Eyebrow color={C.dim}>BATTLE</Eyebrow>
            <Text style={s.cardHeading}>One trick. Stay on it.</Text>
            <Text style={s.body}>Battle mode keeps the whole session centered on one trick without creating a separate session system.</Text>
            <View style={s.actions}><Btn label="Start Battle" variant="red" onPress={() => void openSession("battle")} disabled={busy} /></View>
          </Card>
        ) : null}

        {hasActiveSession ? (
          <>
            <Card>
              <Eyebrow color={C.dim}>CURRENT FOCUS</Eyebrow>
              <Text style={s.cardHeading}>{selectedTrick?.canonicalName ?? "Choose a trick"}</Text>
              <Text style={s.body}>{counts.landed} landed · {counts.missed} missed · {counts.total} attempts</Text>
            </Card>

            {selectedTrick ? (
              <View style={s.attemptRow}>
                <Pressable disabled={busy} onPress={() => void logAttempt(selectedTrick, "landed")} style={({ pressed }) => [s.attemptButton, s.landButton, (pressed || busy) && s.pressed]}>
                  <Text style={s.landText}>LAND</Text>
                </Pressable>
                <Pressable disabled={busy} onPress={() => void logAttempt(selectedTrick, "missed")} style={({ pressed }) => [s.attemptButton, s.missButton, (pressed || busy) && s.pressed]}>
                  <Text style={s.missText}>MISS</Text>
                </Pressable>
              </View>
            ) : null}

            <Card>
              <Eyebrow color={C.dim}>SESSION ACTIONS</Eyebrow>
              <View style={s.actions}>
                <Btn label={selectedTrick ? "Film Clip" : "Choose Trick"} onPress={() => selectedTrick ? router.push("/capture" as never) : router.push("/trick?returnTo=/flow" as never)} disabled={busy} />
                {!isBattle ? <Btn label="Change Trick" variant="ghost" onPress={() => router.push("/trick?returnTo=/flow" as never)} disabled={busy} /> : null}
                <Btn label={isEnding ? "Ending…" : isBattle ? "End Battle" : "End Session"} variant="ghost" onPress={() => void finishSession()} disabled={busy} />
              </View>
            </Card>
          </>
        ) : null}

        <Card>
          <Eyebrow color={C.dim}>LAST RECAP</Eyebrow>
          <Text style={s.body}>Finish a session to review your latest recap and progression.</Text>
          <View style={s.actions}><Btn label="View Session History" variant="ghost" onPress={() => router.push("/history" as never)} /></View>
        </Card>

        {createError ? <Text style={s.error}>{createError}</Text> : null}
        {submitError ? <Text style={s.error}>{submitError}</Text> : null}
        {endError ? <Text style={s.error}>{endError}</Text> : null}
      </ScrollView>
      <AppNav />
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  content: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 28, gap: 18 },
  header: { paddingBottom: 4 },
  title: { fontFamily: F.heading, fontSize: 38, lineHeight: 42, color: C.offwhite },
  subtitle: { fontFamily: F.body, fontSize: 14, color: C.dim, marginTop: 2 },
  welcome: { fontFamily: F.body, fontSize: 16, lineHeight: 23, color: C.offwhite },
  cardHeading: { fontFamily: F.heading, fontSize: 22, lineHeight: 27, color: C.offwhite, marginTop: 8 },
  body: { fontFamily: F.body, fontSize: 14, lineHeight: 21, color: C.dim, marginTop: 6 },
  loading: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 12 },
  actions: { gap: 10, marginTop: 14 },
  attemptRow: { flexDirection: "row", gap: 12 },
  attemptButton: { flex: 1, minHeight: 112, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  landButton: { backgroundColor: C.volt },
  missButton: { backgroundColor: C.charcoal2, borderWidth: 2, borderColor: C.red },
  landText: { fontFamily: F.heading, fontSize: 24, color: C.charcoal },
  missText: { fontFamily: F.heading, fontSize: 24, color: C.red },
  error: { fontFamily: F.body, color: C.red, fontSize: 13, textAlign: "center" },
  pressed: { opacity: 0.72 },
});