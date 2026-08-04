import React, { useEffect } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { C, F, withOpacity } from "../src/theme";
import { Btn, Card, Eyebrow } from "../src/ui";

export default function NotificationsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();

  useEffect(() => {
    track("notifications_viewed");
  }, []);

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <View style={{ gap: 6 }}>
        <Eyebrow color={C.volt}>UPDATES</Eyebrow>
        <Text style={s.title}>Notifications</Text>
        <Text style={s.sub}>Progress and social updates from your skate circle.</Text>
      </View>

      <View style={s.centered}>
        <Card accent={C.volt} style={s.emptyCard}>
          <Eyebrow color={C.volt}>INBOX</Eyebrow>
          <Text style={s.emptyTitle}>No notifications yet.</Text>
          <Text style={s.hint}>
            Push and in-app notifications will appear here when friends react, sessions finish
            analyzing, or battles update. Push is not enabled in Lite yet.
          </Text>
        </Card>
      </View>

      <Btn label="Back" variant="ghost" onPress={() => router.back()} />
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24, gap: 12 },
  title: {
    fontFamily: F.heading,
    fontSize: 28,
    color: C.offwhite,
    textShadowColor: withOpacity(C.volt, 0.3),
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 10,
  },
  sub: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
  centered: { flex: 1, justifyContent: "center" },
  emptyCard: {
    backgroundColor: C.charcoal,
    shadowColor: C.volt,
    shadowOpacity: 0.28,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 0 },
    elevation: 4,
  },
  emptyTitle: { fontFamily: F.bold, fontSize: 16, color: C.offwhite, marginTop: 4 },
  hint: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim, marginTop: 8 },
});
