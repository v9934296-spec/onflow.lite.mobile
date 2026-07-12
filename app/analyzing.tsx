import React, { useEffect, useRef, useState } from "react";
import { Alert, Text, View, StyleSheet } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { mapClipJobToAnalysis } from "../src/analysis/mapClipJobToAnalysis";
import { pollClipJobUntilDone } from "../src/analysis/pollClipJob";
import { C, F } from "../src/theme";
import { getFlowRedirect } from "../src/flow";
import { useSession } from "../src/session";

const LOCAL_STEPS = ["uploading clip", "reading frames", "checking evidence", "writing it straight"];

const JOB_STEPS: Record<string, string> = {
  pending: "queued for analysis",
  processing: "reading your clip",
  completed: "writing it straight",
  failed: "analysis failed",
};

export default function Analyzing() {
  const router = useRouter();
  const { trick, analysis, pendingClipJobId, setAnalysis, setPendingClipJobId } = useSession();
  const [step, setStep] = useState(0);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const pollingRef = useRef(false);

  const redirect = getFlowRedirect("analyzing", { trick, analysis, pendingClipJobId });
  const isApiJob = Boolean(pendingClipJobId);
  const steps = isApiJob
    ? ["uploading clip", jobStatus ? JOB_STEPS[jobStatus] ?? "analyzing" : "queued for analysis", "checking evidence", "writing it straight"]
    : LOCAL_STEPS;

  useEffect(() => {
    setStep(0);
  }, [analysis, pendingClipJobId]);

  useEffect(() => {
    if (!pendingClipJobId || pollingRef.current) return;
    pollingRef.current = true;
    let cancelled = false;

    const run = async () => {
      const res = await pollClipJobUntilDone(pendingClipJobId, {
        onStatus: (status) => {
          if (!cancelled) setJobStatus(status);
        },
      });

      if (cancelled) return;

      if (!res.ok) {
        setPollError(res.error.message);
        return;
      }

      if (res.data.status === "failed") {
        setPollError(res.data.failure_reason);
        return;
      }

      if (res.data.status === "completed") {
        setAnalysis(mapClipJobToAnalysis(res.data, trick!));
        setPendingClipJobId(null);
      }
    };

    void run();
    return () => {
      cancelled = true;
      pollingRef.current = false;
    };
  }, [pendingClipJobId, setAnalysis, setPendingClipJobId, trick]);

  useEffect(() => {
    if (redirect) return;
    if (pollError) {
      Alert.alert("Analysis failed", pollError, [
        { text: "Back to capture", onPress: () => router.replace("/capture") },
      ]);
      setPendingClipJobId(null);
      return;
    }

    if (isApiJob && !analysis) return;

    if (step < steps.length) {
      const timer = setTimeout(() => setStep((current) => current + 1), isApiJob ? 900 : 600);
      return () => clearTimeout(timer);
    }

    const timer = setTimeout(() => router.replace("/result"), 350);
    return () => clearTimeout(timer);
  }, [redirect, router, step, isApiJob, analysis, pollError, setPendingClipJobId, steps.length]);

  if (redirect) return <Redirect href={redirect} />;

  return (
    <View style={s.screen}>
      <Text style={s.trick}>{trick}</Text>
      <Text style={s.called}>{isApiJob ? "CALLED · ONFLOW API" : "CALLED · LITE ENGINE"}</Text>
      {pollError ? <Text style={s.error}>{pollError}</Text> : null}
      <View style={{ gap: 14, marginTop: 20 }}>
        {steps.map((label, index) => (
          <View key={`${label}-${index}`} style={[s.row, { opacity: index <= step ? 1 : 0.25 }]}>
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
  error: { fontFamily: F.body, fontSize: 13, color: C.red, marginTop: 12 },
});
