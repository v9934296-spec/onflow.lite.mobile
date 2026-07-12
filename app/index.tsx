import React, { useEffect, useState } from "react";
import { ActivityIndicator, Alert, Text, View, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { useAccount } from "../src/auth/accountContext";
import { useAuth } from "../src/auth/authContext";
import { getBestTrickStreak, getLast7Days } from "../src/progress";
import { useSkateSession } from "../src/skateSession/skateSessionContext";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow, WeekRow } from "../src/ui";
import { useSession } from "../src/session";
import { useSessionAttempts } from "../src/sessionAttempts/useSessionAttempts";

export default function Home() {
  const router = useRouter();
  const { log, attempts, resetLoop, selectedTrick } = useSession();
  const { user } = useAccount();
  const { signOut } = useAuth();
  const {
    activeSession,
    hasActiveSession,
    hydrateState,
    hydrateError,
    isCreating,
    createError,
    startSession,
    refreshActiveSession,
    endSession,
    isEnding,
    endError,
    dismissEndError,
  } = useSkateSession();
  const {
    counts: sessionCounts,
    isSubmitting: loggingAttempt,
    submitError: attemptError,
    logAttempt,
    dismissSubmitError,
  } = useSessionAttempts(activeSession?.id ?? null);
  const insets = useSafeAreaInsets();
  const [entering, setEntering] = useState(false);
  const week = getLast7Days(attempts);
  const bestStreak = getBestTrickStreak(attempts);

  const sessionBusy = isCreating || entering || loggingAttempt || isEnding;
  const sessionLoading = hydrateState === "loading";

  useEffect(() => {
    track("home_viewed");
  }, []);

  async function enterSession(createIfNeeded: boolean) {
    if (sessionBusy || sessionLoading) return;
    setEntering(true);
    try {
      if (createIfNeeded) {
        const ok = await startSession();
        if (!ok) return;
      } else if (!hasActiveSession) {
        return;
      }
      resetLoop();
      router.push("/trick");
    } finally {
      setEntering(false);
    }
  }

  async function handleEndSession() {
    if (sessionBusy || !hasActiveSession) return;

    const finish = async () => {
      const result = await endSession();
      if (!result.ok) return;
      track("session_ended", {
        session_id: result.recap.session_id,
        attempts: result.recap.attempts_count,
        landed: result.recap.landed_count,
      });
      resetLoop();
      router.replace(`/recap?sessionId=${encodeURIComponent(result.recap.session_id)}`);
    };

    if (sessionCounts.total === 0) {
      Alert.alert(
        "End empty session?",
        "You haven't logged any attempts. End anyway?",
        [
          { text: "Cancel", style: "cancel" },
          { text: "End session", style: "destructive", onPress: () => void finish() },
        ],
      );
      return;
    }

    await finish();
  }

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <View style={s.hero}>
        <Eyebrow>
          <Text style={{ color: C.red }}>■ </Text>ONFLOW / LITE BUILD
        </Eyebrow>
        <Text style={s.h1}>
          Film it.{"\n"}
          <Text style={{ color: C.red }}>Get it straight.</Text>
        </Text>
        <Text style={s.sub}>
          One clip in, honest feedback out. No fake numbers — if we can't see it, we say so.
        </Text>
        {user ? (
          <Text style={s.signedInAs}>
            Signed in as{" "}
            <Text style={{ color: C.offwhite, fontFamily: F.bold }}>
              {user.email || user.user_id}
            </Text>
          </Text>
        ) : null}
      </View>

      {hasActiveSession && activeSession ? (
        <Card accent={C.volt}>
          <Eyebrow color={C.volt}>ACTIVE SESSION</Eyebrow>
          {activeSession.spot_label ? (
            <Text style={s.sessionMeta}>{activeSession.spot_label}</Text>
          ) : null}
          {activeSession.focus_trick ? (
            <Text style={s.sessionMeta}>Focus: {activeSession.focus_trick}</Text>
          ) : null}
          {selectedTrick ? (
            <Text style={s.sessionTrick}>{selectedTrick.canonicalName}</Text>
          ) : null}
          {sessionCounts.total > 0 ? (
            <Text style={s.sessionMeta}>
              {sessionCounts.landed} landed · {sessionCounts.missed} missed · {sessionCounts.total} logged
            </Text>
          ) : (
            <Text style={s.sessionMeta}>No attempts logged yet</Text>
          )}
        </Card>
      ) : null}

      {attempts.length > 0 && (
        <Card>
          <Eyebrow color={C.volt}>LAST 7 DAYS</Eyebrow>
          <WeekRow days={week} />
          {bestStreak ? (
            <Text style={s.streak}>
              {bestStreak.trick} streak:{" "}
              <Text style={{ color: C.volt, fontFamily: F.bold }}>{bestStreak.streak} day{bestStreak.streak === 1 ? "" : "s"}</Text>
            </Text>
          ) : null}
        </Card>
      )}

      {hydrateError ? (
        <View style={{ gap: 8 }}>
          <Text style={s.error}>{hydrateError}</Text>
          <Btn
            label="Retry"
            variant="ghost"
            onPress={() => void refreshActiveSession()}
            disabled={sessionBusy || sessionLoading}
          />
        </View>
      ) : null}
      {createError ? <Text style={s.error}>{createError}</Text> : null}
      {attemptError ? (
        <View style={{ gap: 8 }}>
          <Text style={s.error}>{attemptError}</Text>
          <Btn label="Dismiss" variant="ghost" onPress={dismissSubmitError} />
        </View>
      ) : null}
      {endError ? (
        <View style={{ gap: 8 }}>
          <Text style={s.error}>{endError}</Text>
          <Btn label="Dismiss" variant="ghost" onPress={dismissEndError} />
        </View>
      ) : null}

      <View style={{ gap: 10 }}>
        {sessionLoading ? (
          <View style={s.loadingRow}>
            <ActivityIndicator color={C.volt} />
            <Text style={s.loadingText}>Checking for active session…</Text>
          </View>
        ) : hasActiveSession ? (
          <>
            <Btn
              label={sessionBusy ? "Opening session…" : selectedTrick ? "Change trick" : "Continue session"}
              onPress={() => void (selectedTrick ? router.push("/trick") : enterSession(false))}
              disabled={sessionBusy}
            />
            {selectedTrick ? (
              <>
                <Text style={s.selectedHint}>Current trick: {selectedTrick.canonicalName}</Text>
                <View style={s.outcomeRow}>
                  <Btn
                    label={loggingAttempt ? "Saving…" : "Land"}
                    onPress={() => void logAttempt(selectedTrick, "landed")}
                    disabled={sessionBusy}
                  />
                  <Btn
                    label={loggingAttempt ? "Saving…" : "Miss"}
                    variant="ghost"
                    onPress={() => void logAttempt(selectedTrick, "missed")}
                    disabled={sessionBusy}
                  />
                </View>
              </>
            ) : null}
            <Btn
              label={isEnding ? "Ending session…" : "End session"}
              variant="red"
              onPress={() => void handleEndSession()}
              disabled={sessionBusy}
            />
          </>
        ) : (
          <Btn
            label={sessionBusy ? "Starting session…" : "Start session"}
            onPress={() => void enterSession(true)}
            disabled={sessionBusy}
          />
        )}
        <Btn
          label={`Session log${log.length > 0 ? ` · ${log.length}` : ""}`}
          variant="ghost"
          onPress={() => {
            track("log_viewed");
            router.push("/log");
          }}
        />
        <Btn label="Sign out" variant="ghost" onPress={() => void signOut()} />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24, gap: 16 },
  hero: { flex: 1, justifyContent: "center", gap: 10 },
  h1: { fontFamily: F.heading, fontSize: 40, lineHeight: 44, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 14, lineHeight: 21, color: C.dim },
  signedInAs: { fontFamily: F.body, fontSize: 12, color: C.dim, marginTop: 4 },
  streak: { fontFamily: F.body, fontSize: 13, color: C.dim, marginTop: 4 },
  sessionMeta: { fontFamily: F.body, fontSize: 13, color: C.dim, marginTop: 2 },
  sessionTrick: { fontFamily: F.bold, fontSize: 16, color: C.offwhite, marginTop: 4 },
  selectedHint: { fontFamily: F.body, fontSize: 12, color: C.dim, textAlign: "center" },
  outcomeRow: { flexDirection: "row", gap: 10 },
  error: { fontFamily: F.body, fontSize: 13, lineHeight: 18, color: C.red, textAlign: "center" },
  loadingRow: { flexDirection: "row", alignItems: "center", gap: 10, justifyContent: "center", paddingVertical: 12 },
  loadingText: { fontFamily: F.body, fontSize: 13, color: C.dim },
});
