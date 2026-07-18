import React, { useEffect } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { useSkateSession } from "../src/skateSession/skateSessionContext";
import { formatSessionHistorySubtitle, formatSessionHistoryTitle } from "../src/sessionHistory/sessionHistoryFormat";
import { useSessionHistory } from "../src/sessionHistory/useSessionHistory";
import { C, F } from "../src/theme";
import { Btn, Eyebrow } from "../src/ui";

export default function SessionHistory() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { activeSession } = useSkateSession();
  const { sessions, isLoading, error, refresh } = useSessionHistory(activeSession?.id ?? null);

  useEffect(() => { track("session_history_viewed"); }, []);

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}> 
      <View style={{ gap: 6 }}>
        <Eyebrow color={C.volt}>PROGRESSION</Eyebrow>
        <Text style={s.title}>Session history</Text>
        <Text style={s.sub}>Your completed sessions. Tap one to reopen the recap and see exactly what was logged.</Text>
      </View>

      {isLoading ? (
        <View style={s.centered}><ActivityIndicator color={C.volt} /><Text style={s.sub}>Loading history…</Text></View>
      ) : error ? (
        <View style={[s.centered, { gap: 10 }]}><Text style={s.error}>{error}</Text><Btn label="Retry" variant="ghost" onPress={() => void refresh()} /></View>
      ) : sessions.length === 0 ? (
        <View style={s.centered}><Eyebrow color={C.red}>NO SESSIONS</Eyebrow><Text style={s.emptyTitle}>Go build the first one.</Text><Text style={s.sub}>Finish a session and it will land here automatically.</Text></View>
      ) : (
        <ScrollView contentContainerStyle={{ gap: 10, paddingBottom: 12 }} showsVerticalScrollIndicator={false}>
          {sessions.map((session, index) => (
            <Pressable
              key={session.session_id}
              onPress={() => { track("session_history_opened", { session_id: session.session_id }); router.push(`/recap?sessionId=${encodeURIComponent(session.session_id)}` as never); }}
              style={({ pressed }) => [s.row, pressed && { opacity: 0.72 }]}
            >
              <Text style={s.index}>{String(sessions.length - index).padStart(2, "0")}</Text>
              <View style={{ flex: 1, gap: 3 }}><Text style={s.rowTitle}>{formatSessionHistoryTitle(session)}</Text><Text style={s.rowSub}>{formatSessionHistorySubtitle(session)}</Text></View>
              <Text style={s.chevron}>›</Text>
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
  title: { fontFamily: F.heading, fontSize: 32, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", gap: 8 },
  emptyTitle: { fontFamily: F.bold, fontSize: 17, color: C.offwhite },
  error: { fontFamily: F.body, fontSize: 13, lineHeight: 18, color: C.red, textAlign: "center" },
  row: { flexDirection: "row", alignItems: "center", gap: 12, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 14, backgroundColor: C.charcoal2, borderLeftWidth: 3, borderLeftColor: C.volt },
  index: { fontFamily: F.mono, fontSize: 10, color: C.red },
  rowTitle: { fontFamily: F.bold, fontSize: 15, color: C.offwhite },
  rowSub: { fontFamily: F.body, fontSize: 12, color: C.dim },
  chevron: { fontFamily: F.body, fontSize: 24, color: C.dim },
});
