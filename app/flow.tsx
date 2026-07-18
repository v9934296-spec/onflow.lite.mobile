import React, { useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, Text, View } from "react-native";
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
    <View style={[s.screen, { paddingTop: insets.top + 12, paddingBottom: insets.bottom }]}> 
      <View style={s.content}>
        <View style={s.header}>
          <Eyebrow color={isBattle ? C.red : C.volt}>ONFLOW / FLOW</Eyebrow>
          <Text style={s.title}>{hasActiveSession ? (isBattle ? "Battle in progress." : "Session in progress.") : "Choose your mode."}</Text>
          <Text style={s.sub}>
            {hasActiveSession
              ? "Log the truth fast. Film when you want evidence."
              : "Session is open practice. Battle locks your attention onto one trick until you end it."}
          </Text>
        </View>

        {hydrateState === "loading" ? (
          <View style={s.loading}><ActivityIndicator color={C.volt} /><Text style={s.sub}>Loading session…</Text></View>
        ) : !hasActiveSession ? (
          <View style={s.modeGrid}>
            <Pressable onPress={() => void openSession("session")} style={({ pressed }) => [s.modeCard, pressed && s.pressed]}>
              <Eyebrow color={C.volt}>SESSION</Eyebrow>
              <Text style={s.modeTitle}>Skate freely.</Text>
              <Text style={s.modeCopy}>Change tricks whenever you want. Log attempts, film clips, finish with a recap.</Text>
              <Text style={[s.modeAction, { color: C.volt }]}>START SESSION →</Text>
            </Pressable>
            <Pressable onPress={() => void openSession("battle")} style={({ pressed }) => [s.modeCard, s.battleCard, pressed && s.pressed]}>
              <Eyebrow color={C.red}>BATTLE</Eyebrow>
              <Text style={s.modeTitle}>One trick. Stay on it.</Text>
              <Text style={s.modeCopy}>Pick the trick you are fighting today and keep the whole session centered on it.</Text>
              <Text style={[s.modeAction, { color: C.red }]}>START BATTLE →</Text>
            </Pressable>
          </View>
        ) : (
          <>
            <Card accent={isBattle ? C.red : C.volt}>
              <Eyebrow color={isBattle ? C.red : C.volt}>{isBattle ? "ACTIVE BATTLE" : "ACTIVE SESSION"}</Eyebrow>
              <Text style={s.trick}>{selectedTrick?.canonicalName ?? "Choose a trick"}</Text>
              <Text style={s.stats}>{counts.landed} landed · {counts.missed} missed · {counts.total} attempts</Text>
            </Card>

            {selectedTrick ? (
              <View style={s.attemptRow}>
                <Pressable
                  disabled={busy}
                  onPress={() => void logAttempt(selectedTrick, "landed")}
                  style={({ pressed }) => [s.attemptButton, s.landButton, (pressed || busy) && s.pressed]}
                >
                  <Text style={s.landText}>LAND</Text>
                </Pressable>
                <Pressable
                  disabled={busy}
                  onPress={() => void logAttempt(selectedTrick, "missed")}
                  style={({ pressed }) => [s.attemptButton, s.missButton, (pressed || busy) && s.pressed]}
                >
                  <Text style={s.missText}>MISS</Text>
                </Pressable>
              </View>
            ) : null}

            <View style={{ gap: 10 }}>
              <Btn label={selectedTrick ? "Film this attempt" : "Choose trick"} onPress={() => selectedTrick ? router.push("/capture" as never) : router.push("/trick?returnTo=/flow" as never)} disabled={busy} />
              {!isBattle ? <Btn label="Change trick" variant="ghost" onPress={() => router.push("/trick?returnTo=/flow" as never)} disabled={busy} /> : null}
              <Btn label={isEnding ? "Ending…" : isBattle ? "End battle" : "End session"} variant="red" onPress={() => void finishSession()} disabled={busy} />
            </View>
          </>
        )}

        {createError ? <Text style={s.error}>{createError}</Text> : null}
        {submitError ? <Text style={s.error}>{submitError}</Text> : null}
        {endError ? <Text style={s.error}>{endError}</Text> : null}
      </View>
      <AppNav />
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  content: { flex: 1, paddingHorizontal: 24, paddingTop: 16, gap: 18 },
  header: { gap: 8 },
  title: { fontFamily: F.heading, fontSize: 34, lineHeight: 38, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 14, lineHeight: 21, color: C.dim },
  loading: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 20 },
  modeGrid: { gap: 12 },
  modeCard: { backgroundColor: C.charcoal2, borderRadius: 14, padding: 20, gap: 10, borderLeftWidth: 4, borderLeftColor: C.volt },
  battleCard: { borderLeftColor: C.red },
  modeTitle: { fontFamily: F.heading, fontSize: 23, color: C.offwhite },
  modeCopy: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
  modeAction: { fontFamily: F.bold, fontSize: 13, marginTop: 4 },
  trick: { fontFamily: F.heading, fontSize: 26, color: C.offwhite, marginTop: 4 },
  stats: { fontFamily: F.mono, fontSize: 11, color: C.dim, marginTop: 4 },
  attemptRow: { flexDirection: "row", gap: 12 },
  attemptButton: { flex: 1, minHeight: 112, borderRadius: 16, alignItems: "center", justifyContent: "center" },
  landButton: { backgroundColor: C.volt },
  missButton: { backgroundColor: C.charcoal2, borderWidth: 2, borderColor: C.red },
  landText: { fontFamily: F.heading, fontSize: 24, color: C.charcoal },
  missText: { fontFamily: F.heading, fontSize: 24, color: C.red },
  error: { fontFamily: F.body, color: C.red, fontSize: 13, textAlign: "center" },
  pressed: { opacity: 0.72 },
});
