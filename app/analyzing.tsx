import React, { useEffect, useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Redirect, useRouter } from "expo-router";

import { clearPendingAnalysisJob } from "../src/analysis/pendingAnalysisStore";
import { mapClipJobToAnalysis } from "../src/analysis/mapClipJobToAnalysis";
import { pollClipJobUntilDone } from "../src/analysis/pollClipJob";
import { useAccount } from "../src/auth/accountContext";
import { getFlowRedirect } from "../src/flowGuard";
import { useSession } from "../src/session";
import { C, F } from "../src/theme";
import { Btn } from "../src/ui";

const LOCAL_STEPS = ["uploading clip", "reading frames", "checking evidence", "writing it straight"];

const JOB_STEPS: Record<string, string> = {
  pending: "queued for analysis",
  processing: "reading your clip",
  completed: "writing it straight",
  failed: "analysis failed",
};

export default function Analyzing() {
  const router = useRouter();
  const { user } = useAccount();
  const { trick, analysis, pendingClipJobId, setAnalysis, setPendingClipJobId } = useSession();
  const [step, setStep] = useState(0);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [canRetry, setCanRetry] = useState(false);
  const [retryNonce, setRetryNonce] = useState(0);
  const pollingRef = useRef(false);

  const redirect = getFlowRedirect("analyzing", { trick, analysis, pendingClipJobId });
  const isApiJob = Boolean(pendingClipJobId);
  const steps = isApiJob
    ? [
        "uploading clip",
        jobStatus ? JOB_STEPS[jobStatus] ?? "analyzing" : "queued for analysis",
        "checking evidence",
        "writing it straight",
      ]
    : LOCAL_STEPS;

  const clearPersistedJob = async (clearState: boolean): Promise<boolean> => {
    if (user?.user_id) {
      const result = await clearPendingAnalysisJob(user.user_id);
      if (!result.ok) {
        setPollError(result.error);
        setCanRetry(true);
        return false;
      }
    }
    if (clearState) setPendingClipJobId(null);
    return true;
  };

  const discardAndCaptureAgain = async () => {
    const cleared = await clearPersistedJob(true);
    if (!cleared) return;
    setAnalysis(null);
    router.replace("/capture");
  };

  const leaveTerminalFailure = (destination: "/" | "/capture") => {
    setPendingClipJobId(null);
    setAnalysis(null);
    router.replace(destination);
  };

  useEffect(() => {
    setStep(0);
  }, [analysis, pendingClipJobId]);

  useEffect(() => {
    if (!pendingClipJobId || !trick || pollingRef.current) return;
    pollingRef.current = true;
    const controller = new AbortController();
    let cancelled = false;

    setPollError(null);
    setCanRetry(false);

    const run = async () => {
      const res = await pollClipJobUntilDone(pendingClipJobId, {
        signal: controller.signal,
        onStatus: (status) => {
          if (!cancelled) setJobStatus(status);
        },
      });

      if (cancelled || controller.signal.aborted) return;

      if (!res.ok) {
        const retryable =
          res.error.kind === "timeout" ||
          res.error.kind === "network" ||
          res.error.kind === "server";
        setCanRetry(retryable);
        setPollError(res.error.message);
        if (!retryable) await clearPersistedJob(false);
        return;
      }

      if (res.data.status === "failed") {
        setPollError(res.data.failure_reason);
        setCanRetry(false);
        await clearPersistedJob(false);
        return;
      }

      if (res.data.status === "completed") {
        setAnalysis(mapClipJobToAnalysis(res.data, trick));
        await clearPersistedJob(true);
      }
    };

    void run().finally(() => {
      pollingRef.current = false;
    });

    return () => {
      cancelled = true;
      controller.abort();
      pollingRef.current = false;
    };
  }, [pendingClipJobId, retryNonce, setAnalysis, setPendingClipJobId, trick, user?.user_id]);

  useEffect(() => {
    if (redirect || pollError) return;
    if (isApiJob && !analysis) return;

    if (step < steps.length) {
      const timer = setTimeout(() => setStep((current) => current + 1), isApiJob ? 900 : 600);
      return () => clearTimeout(timer);
    }

    const timer = setTimeout(() => router.replace("/result"), 350);
    return () => clearTimeout(timer);
  }, [redirect, router, step, isApiJob, analysis, pollError, steps.length]);

  if (redirect) return <Redirect href={redirect} />;

  return (
    <View style={s.screen}>
      <Text style={s.trick}>{trick}</Text>
      <Text style={s.called}>{isApiJob ? "CALLED · ONFLOW API" : "CALLED · LITE ENGINE"}</Text>

      {pollError ? (
        <View style={s.errorBlock}>
          <Text style={s.error}>{pollError}</Text>
          {canRetry ? (
            <>
              <Btn
                label="Retry analysis check"
                onPress={() => {
                  setPollError(null);
                  setRetryNonce((value) => value + 1);
                }}
              />
              <Btn
                label="Discard and re-film"
                variant="red"
                onPress={() => void discardAndCaptureAgain()}
              />
              <Btn label="Back home" variant="ghost" onPress={() => router.replace("/")} />
            </>
          ) : (
            <>
              <Btn label="Back to capture" onPress={() => leaveTerminalFailure("/capture")} />
              <Btn
                label="Back home"
                variant="ghost"
                onPress={() => leaveTerminalFailure("/")}
              />
            </>
          )}
        </View>
      ) : (
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
      )}
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
  errorBlock: { gap: 12, marginTop: 20 },
  error: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.red },
});
