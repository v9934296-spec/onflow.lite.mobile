import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { C, F } from "../src/theme";
import { Btn, Eyebrow } from "../src/ui";
import { useSession } from "../src/session";

export default function Home() {
  const router = useRouter();
  const { log, resetLoop } = useSession();
  const insets = useSafeAreaInsets();

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
      </View>
      <View style={{ gap: 10 }}>
        <Btn
          label="Film a clip"
          onPress={() => {
            resetLoop();
            router.push("/trick");
          }}
        />
        <Btn
          label={`Session log${log.length > 0 ? ` · ${log.length}` : ""}`}
          variant="ghost"
          onPress={() => router.push("/log")}
        />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24 },
  hero: { flex: 1, justifyContent: "center", gap: 10 },
  h1: { fontFamily: F.heading, fontSize: 40, lineHeight: 44, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 14, lineHeight: 21, color: C.dim },
});
