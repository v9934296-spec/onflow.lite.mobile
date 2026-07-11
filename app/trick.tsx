import React from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { C, F } from "../src/theme";
import { Btn, Eyebrow } from "../src/ui";
import { TRICKS } from "../src/engine";
import { useSession } from "../src/session";

export default function TrickPicker() {
  const router = useRouter();
  const { setTrick } = useSession();
  const insets = useSafeAreaInsets();

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <View style={{ gap: 6 }}>
        <Eyebrow>STEP 1 · CALL IT</Eyebrow>
        <Text style={s.title}>What are you filming?</Text>
        <Text style={s.sub}>
          Call the trick before you film it. The analysis checks the footage against your call.
        </Text>
      </View>
      <View style={s.grid}>
        {TRICKS.map((t) => (
          <Pressable
            key={t}
            style={({ pressed }) => [s.trickBtn, { opacity: pressed ? 0.75 : 1 }]}
            onPress={() => {
              track("trick_selected", { trick: t });
              setTrick(t);
              router.push("/capture");
            }}
          >
            <Text style={s.trickText}>{t}</Text>
          </Pressable>
        ))}
      </View>
      <View style={{ marginTop: "auto" }}>
        <Btn label="Back" variant="ghost" onPress={() => router.back()} />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24, gap: 16 },
  title: { fontFamily: F.heading, fontSize: 24, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  trickBtn: {
    width: "48%",
    backgroundColor: C.charcoal2,
    borderWidth: 1,
    borderColor: C.aluminum,
    borderRadius: 10,
    paddingVertical: 16,
    alignItems: "center",
  },
  trickText: { fontFamily: F.bold, fontSize: 14, color: C.offwhite },
});
