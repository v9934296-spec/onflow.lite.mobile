import React, { useEffect, useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { C, F } from "../src/theme";
import { getFlowRedirect } from "../src/flow";
import { useSession } from "../src/session";

const STEPS = ["uploading clip", "reading frames", "checking evidence", "writing it straight"];

export default function Analyzing() {
  const router = useRouter();
  const { trick, analysis } = useSession();
  const [step, setStep] = useState(0);

  const redirect = getFlowRedirect("analyzing", { trick, analysis });

  useEffect(() => {
    setStep(0);
  }, [analysis]);

  useEffect(() => {
    if (redirect) return;

    if (step < STEPS.length) {
      const timer = setTimeout(() => setStep((current) => current + 1), 600);
      return () => clearTimeout(timer);
    }

    const timer = setTimeout(() => router.replace("/result"), 350);
    return () => clearTimeout(timer);
  }, [redirect, router, step]);

  if (redirect) return <Redirect href={redirect} />;

  return (
    <View style={s.screen}>
      <Text style={s.trick}>{trick}</Text>
      <Text style={s.called}>CALLED · LITE ENGINE</Text>
      <View style={{ gap: 14, marginTop: 20 }}>
        {STEPS.map((label, index) => (
          <View key={label} style={[s.row, { opacity: index <= step ? 1 : 0.25 }]}>
            <Text style={[s.box, { color: index < step ? C.volt : C.dim }]}>
              {index < step ? "■" : "□"}
            </Text>
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
