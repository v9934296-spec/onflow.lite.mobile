import React, { useEffect } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { useSkateSession } from "../src/skateSession/skateSessionContext";
import {
  formatSessionHistorySubtitle,
  formatSessionHistoryTitle,
} from "../src/sessionHistory/sessionHistoryFormat";
import { useSessionHistory } from "../src/sessionHistory/useSessionHistory";
import { C, F } from "../src/theme";
import { Btn, Eyebrow } from "../src/ui";

export default function SessionHistory() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { activeSession } = useSkateSession();
  const { sessions, isLoading, error, refresh } = useSessionHistory(activeSession?.id ?? null);

  useEffect(() => {
    track("session_history_viewed");
  }, []);

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <View style={{ gap: 6 }}>
        <Eyebrow>PROGRESSION</Eyebrow>
        <Text style={s.title}>Session history</Text>
        <Text style={s.sub}>Completed sessions on this device. Tap one to reopen its recap.</Text>
      </View>

      {isLoading ? (
        <View style={s.centered}>
          <ActivityIndicator color={C.volt} />
          <Text style={s.sub}>Loading history…</Text>
        </View>
      ) : error ? (
        <View style={[s.centered, { gap: 10 }]}>
          <Text style={s.error}>{error}</Text>
          <Btn label="Retry" variant="ghost" onPress={() => void refresh()} />
        </View>
      ) : sessions.length === 0 ? (
        <View style={s.centered}>
          <Text style={s.emptyTitle}>No sessions yet</Text>
          <Text style={s.sub}>Finish a session to build your history here.</Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ gap: 10, paddingBottom: 12 }}>
          {sessions.map((session) => (
            <Pressable
              key={session.session_id}
              onPress={() => {
                track("session_history_opened", { session_id: session.session_id });
                router.push(`/recap?sessionId=${encodeURIComponent(session.session_id)}`);
              }}
              style={({ pressed }) => [s.row, pressed && { opacity: 0.75 }]}
            >
              <Text style={s.rowTitle}>{formatSessionHistoryTitle(session)}</Text>
              <Text style={s.rowSub}>{formatSessionHistorySubtitle(session)}</Text>
            </Pressable>
          ))}
        </ScrollView>
      )}

      <Btn label="Back" variant="ghost" onPress={() => router.back()} />
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24, gap: 14 },
  title: { fontFamily: F.heading, fontSize: 24, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", gap: 8 },
  emptyTitle: { fontFamily: F.bold, fontSize: 16, color: C.offwhite },
  error: { fontFamily: F.body, fontSize: 13, lineHeight: 18, color: C.red, textAlign: "center" },
  row: {
    borderWidth: 1,
    borderColor: C.aluminum,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: C.charcoal2,
    gap: 4,
  },
  rowTitle: { fontFamily: F.bold, fontSize: 15, color: C.offwhite },
  rowSub: { fontFamily: F.body, fontSize: 12, color: C.dim },
});
