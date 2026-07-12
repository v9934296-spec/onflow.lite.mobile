import React, { useEffect } from "react";
import { View, Text, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { useAccount } from "../src/auth/accountContext";
import { useAuth } from "../src/auth/authContext";
import { getBestTrickStreak, getLast7Days } from "../src/progress";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow, WeekRow } from "../src/ui";
import { useSession } from "../src/session";

export default function Home() {
  const router = useRouter();
  const { log, attempts, resetLoop } = useSession();
  const { user } = useAccount();
  const { signOut } = useAuth();
  const insets = useSafeAreaInsets();
  const week = getLast7Days(attempts);
  const bestStreak = getBestTrickStreak(attempts);

  useEffect(() => {
    track("home_viewed");
  }, []);

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
        {user?.email ? (
          <Text style={s.signedInAs}>
            Signed in as <Text style={{ color: C.offwhite, fontFamily: F.bold }}>{user.email}</Text>
          </Text>
        ) : null}
      </View>

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

      <View style={{ gap: 10 }}>
        <Btn
          label="Film a clip"
          onPress={() => {
            track("clip_film_started");
            resetLoop();
            router.push("/trick");
          }}
        />
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
});
