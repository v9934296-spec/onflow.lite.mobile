import React, { useEffect, useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { C, F } from "../src/theme";
import { useSession } from "../src/session";

const STEPS = ["uploading clip", "reading frames", "checking evidence", "writing it straight"];

export default function Analyzing() {
  const router = useRouter();
  const { trick, analysis } = useSession();
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!analysis) {
      router.replace("/");
      return;
    }
    if (step < STEPS.length) {
      const t = setTimeout(() => setStep((s) => s + 1), 600);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => router.replace("/result"), 350);
    return () => clearTimeout(t);
  }, [step, analysis]);

  return (
    <View style={s.screen}>
      <Text style={s.trick}>{trick}</Text>
      <Text style={s.called}>CALLED · LITE ENGINE</Text>
      <View style={{ gap: 14, marginTop: 20 }}>
        {STEPS.map((label, i) => (
          <View key={label} style={[s.row, { opacity: i <= step ? 1 : 0.25 }]}>
            <Text style={[s.box, { color: i < step ? C.volt : C.dim }]}>{i < step ? "■" : "□"}</Text>
            <Text style={s.stepText}>{label}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, justifyContent: "center", paddingHorizontal: 24 },
  trick: { fontFamily: F.heading, fontSize: 24, color: C.offwhite },
  called: { fontFamily: F.mono, fontSize: 11, color: C.dim, letterSpacing: 1, marginTop: 4 },
  row: { flexDirection: "row", alignItems: "center", gap: 10 },
  box: { fontFamily: F.mono, fontSize: 13 },
  stepText: { fontFamily: F.mono, fontSize: 13, color: C.offwhite },
});
