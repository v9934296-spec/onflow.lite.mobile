import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppNav } from "../src/components/AppNav";
import { CurrentFocusHeader } from "../src/components/CurrentFocusHeader";
import { MomentumChip } from "../src/components/MomentumChip";
import { createSkateSession } from "../src/api/sessionApi";
import {
  fetchProgressionTimeline,
  fetchTrickStats,
  fetchWhatsNext,
  type ProgressionTimelineItem,
} from "../src/api/progressionApi";
import { saveActiveSessionId } from "../src/activeSessionStore";
import { useAccount } from "../src/auth/accountContext";
import { useSkateSession } from "../src/skateSession/skateSessionContext";
import { useSessionAttempts } from "../src/sessionAttempts/useSessionAttempts";
import { useSession } from "../src/session";
import {
  adaptTrickStats,
  buildCurrentFocus,
  formatTrickDisplay,
  pickActiveBattle,
} from "../src/progressionAdapter";
import { C, F, RADIUS, SPACE, withOpacity } from "../src/theme";
import { Btn, Card, Eyebrow, SkeletonLines } from "../src/ui";

export default function FlowScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAccount();
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
  const [refreshing, setRefreshing] = useState(false);
  const [lastRecap, setLastRecap] = useState<ProgressionTimelineItem | null>(null);
  const [focusReady, setFocusReady] = useState(false);
  const [focus, setFocus] = useState(buildCurrentFocus(null, []));
  const [battleTrick, setBattleTrick] = useState<string | null>(null);

  const isBattle = activeSession?.notes?.startsWith("[battle]") ?? false;
  const busy = isCreating || startingBattle || isSubmitting || isEnding || hydrateState === "loading";

  const loadHub = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    const [timeline, tricks, whatsNext] = await Promise.all([
      fetchProgressionTimeline(1, 1),
      fetchTrickStats(),
      fetchWhatsNext(),
    ]);
    setLastRecap(timeline.ok && timeline.data.items[0] ? timeline.data.items[0] : null);
    const raw = tricks.ok ? tricks.data : [];
    const adapted = adaptTrickStats(raw);
    setFocus(buildCurrentFocus(whatsNext.ok ? whatsNext.data : null, raw));
    setBattleTrick(pickActiveBattle(adapted)?.display_name ?? null);
    setFocusReady(true);
    setRefreshing(false);
  }, []);

  useEffect(() => {
    void loadHub();
  }, [loadHub]);

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
      if (!user?.user_id) {
        Alert.alert("Could not start battle", "Sign in required.");
        return;
      }
      const result = await createSkateSession({ notes: "[battle] Single-trick battle session" });
      if (!result.ok) {
        Alert.alert("Could not start battle", result.error.message);
        return;
      }
      await saveActiveSessionId(user.user_id, result.data.id);
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

  const landRate = counts.total > 0 ? Math.round((counts.landed / counts.total) * 100) : null;

  return (
    <View style={[s.screen, { paddingTop: insets.top + 12, paddingBottom: insets.bottom }]}>
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={s.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => void loadHub(true)} tintColor={C.volt} />
        }
      >
        <View style={s.header}>
          <Eyebrow color={hasActiveSession ? (isBattle ? C.red : C.volt) : C.volt}>
            {hasActiveSession ? (isBattle ? "BATTLE LIVE" : "SESSION LIVE") : "ONFLOW"}
          </Eyebrow>
          <Text style={s.title}>Flow</Text>
          <Text style={s.sub}>
            {hasActiveSession
              ? "Log the truth fast. Film when you want evidence."
              : "Session is open practice. Battle locks attention onto one trick."}
          </Text>
        </View>

        {!focusReady ? (
          <Card>
            <SkeletonLines />
          </Card>
        ) : (
          <CurrentFocusHeader focus={focus} onPress={() => void openSession(battleTrick ? "battle" : "session")} />
        )}

        {hydrateState === "loading" ? (
          <View style={s.loading}>
            <ActivityIndicator color={C.volt} />
            <Text style={s.sub}>Loading session…</Text>
          </View>
        ) : !hasActiveSession ? (
          <View style={s.modeGrid}>
            <Pressable
              onPress={() => void openSession("session")}
              style={({ pressed }) => [s.modeCard, pressed && s.pressed]}
            >
              <Eyebrow color={C.volt}>SESSION</Eyebrow>
              <Text style={s.modeTitle}>Skate freely.</Text>
              <Text style={s.modeCopy}>
                Change tricks whenever you want. Log attempts, film clips, finish with a recap.
              </Text>
              <Text style={[s.modeAction, { color: C.volt }]}>START SESSION →</Text>
            </Pressable>
            <Pressable
              onPress={() => void openSession("battle")}
              style={({ pressed }) => [s.modeCard, s.battleCard, pressed && s.pressed]}
            >
              <Eyebrow color={C.red}>BATTLE</Eyebrow>
              <Text style={s.modeTitle}>
                {battleTrick ? `Stay on ${battleTrick}.` : "One trick. Stay on it."}
              </Text>
              <Text style={s.modeCopy}>
                Pick the trick you are fighting today and keep the whole session centered on it.
              </Text>
              <Text style={[s.modeAction, { color: C.red }]}>START BATTLE →</Text>
            </Pressable>

            {lastRecap ? (
              <Card
                accent={C.volt}
                onPress={() =>
                  router.push(`/recap?sessionId=${encodeURIComponent(lastRecap.session_id)}` as never)
                }
              >
                <Eyebrow color={C.volt}>LAST RECAP</Eyebrow>
                <Text style={s.modeTitle}>
                  {lastRecap.focus_trick
                    ? formatTrickDisplay(lastRecap.focus_trick)
                    : lastRecap.spot ?? "Recent session"}
                </Text>
                <Text style={s.modeCopy}>
                  {lastRecap.ended_at
                    ? new Date(lastRecap.ended_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                      })
                    : "Recent"}
                  {lastRecap.best_pte_score != null ? ` · PTE ${lastRecap.best_pte_score}` : ""}
                  {lastRecap.attempt_count ? ` · ${lastRecap.attempt_count} attempts` : ""}
                  {lastRecap.clips_count ? ` · ${lastRecap.clips_count} clips` : ""}
                </Text>
              </Card>
            ) : null}
          </View>
        ) : (
          <>
            <Card accent={isBattle ? C.red : C.volt}>
              <View style={s.activeTop}>
                <Eyebrow color={isBattle ? C.red : C.volt}>
                  {isBattle ? "ACTIVE BATTLE" : "ACTIVE SESSION"}
                </Eyebrow>
                {landRate != null && landRate >= 60 ? (
                  <MomentumChip state={landRate >= 80 ? "dialed" : "heating_up"} size="sm" />
                ) : null}
              </View>
              <Text style={s.trick}>{selectedTrick?.canonicalName ?? "Choose a trick"}</Text>
              <Text style={s.stats}>
                <Text style={{ color: C.volt }}>{counts.landed}</Text> landed ·{" "}
                <Text style={{ color: C.red }}>{counts.missed}</Text> missed · {counts.total} attempts
                {landRate != null ? (
                  <Text style={{ color: landRate >= 50 ? C.volt : C.red }}>{` · ${landRate}%`}</Text>
                ) : null}
              </Text>
              {landRate != null ? (
                <View style={s.rateTrack}>
                  <View
                    style={[
                      s.rateFill,
                      {
                        width: `${landRate}%`,
                        backgroundColor: landRate >= 50 ? C.volt : C.red,
                      },
                    ]}
                  />
                </View>
              ) : null}
            </Card>

            {selectedTrick ? (
              <View style={s.attemptStack}>
                <Pressable
                  disabled={busy}
                  onPress={() => void logAttempt(selectedTrick, "missed")}
                  style={({ pressed }) => [
                    s.missButton,
                    (pressed || busy) && s.pressed,
                    pressed && !busy ? s.snap : null,
                  ]}
                >
                  <Text style={s.missText}>MISS</Text>
                </Pressable>
                <Pressable
                  disabled={busy}
                  onPress={() => void logAttempt(selectedTrick, "landed")}
                  style={({ pressed }) => [
                    s.landButton,
                    (pressed || busy) && s.pressed,
                    pressed && !busy ? s.snap : null,
                  ]}
                >
                  <Text style={s.landText}>LAND</Text>
                </Pressable>
              </View>
            ) : null}

            <View style={{ gap: 10 }}>
              <Btn
                label={selectedTrick ? "Film this attempt" : "Choose trick"}
                onPress={() =>
                  selectedTrick
                    ? router.push("/capture" as never)
                    : router.push("/trick?returnTo=/flow" as never)
                }
                disabled={busy}
              />
              {!isBattle ? (
                <Btn
                  label="Change trick"
                  variant="ghost"
                  onPress={() => router.push("/trick?returnTo=/flow" as never)}
                  disabled={busy}
                />
              ) : null}
              <Btn
                label={isEnding ? "Ending…" : isBattle ? "End battle" : "End session"}
                variant="red"
                onPress={() => void finishSession()}
                disabled={busy}
              />
            </View>
          </>
        )}

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
  content: { paddingHorizontal: SPACE.lg, paddingTop: SPACE.md, paddingBottom: SPACE.xl, gap: SPACE.lg },
  header: { gap: SPACE.sm },
  title: {
    fontFamily: F.heading,
    fontSize: 34,
    lineHeight: 38,
    color: C.offwhite,
    textTransform: "uppercase",
  },
  sub: { fontFamily: F.body, fontSize: 14, lineHeight: 21, color: C.dim },
  loading: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 20 },
  modeGrid: { gap: SPACE.md },
  modeCard: {
    backgroundColor: C.charcoal,
    borderRadius: RADIUS.sm,
    padding: SPACE.xl,
    gap: SPACE.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.charcoal4,
    borderLeftWidth: 3,
    borderLeftColor: C.volt,
  },
  battleCard: {
    borderLeftColor: C.red,
    borderColor: withOpacity(C.red, 0.4),
  },
  modeTitle: { fontFamily: F.heading, fontSize: 22, color: C.offwhite, textTransform: "uppercase" },
  modeCopy: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
  modeAction: { fontFamily: F.bold, fontSize: 13, marginTop: 4 },
  activeTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  trick: {
    fontFamily: F.heading,
    fontSize: 28,
    color: C.offwhite,
    marginTop: 4,
    textTransform: "uppercase",
  },
  stats: { fontFamily: F.mono, fontSize: 11, color: C.dim, marginTop: 4 },
  rateTrack: {
    height: 4,
    borderRadius: RADIUS.xs,
    backgroundColor: C.charcoal4,
    overflow: "hidden",
    marginTop: 10,
  },
  rateFill: { height: "100%", borderRadius: RADIUS.xs },
  attemptStack: { gap: 10 },
  missButton: {
    minHeight: 56,
    borderRadius: RADIUS.sm,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: C.charcoal,
    borderWidth: 2,
    borderColor: C.red,
  },
  landButton: {
    minHeight: 96,
    borderRadius: RADIUS.sm,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: C.volt,
  },
  landText: {
    fontFamily: F.heading,
    fontSize: 28,
    color: C.charcoal,
    letterSpacing: 1.2,
  },
  missText: {
    fontFamily: F.heading,
    fontSize: 20,
    color: C.red,
    letterSpacing: 1,
  },
  error: { fontFamily: F.body, color: C.red, fontSize: 13, textAlign: "center" },
  pressed: { opacity: 0.85 },
  snap: { transform: [{ scale: 0.97 }] },
});
