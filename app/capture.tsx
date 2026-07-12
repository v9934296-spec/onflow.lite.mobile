import React, { useState } from "react";
import { Alert, Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as FileSystem from "expo-file-system";
import * as ImagePicker from "expo-image-picker";

import {
  clearPendingAnalysisJob,
  savePendingAnalysisJob,
} from "../src/analysis/pendingAnalysisStore";
import { track } from "../src/analytics";
import { uploadClipToSession } from "../src/api/clipApi";
import { useAccount } from "../src/auth/accountContext";
import { isQuotaExceededMessage, PAYWALL_ROUTE } from "../src/billing/quota";
import { SAMPLE_CLIPS, analyzeSample, analyzeUserClip } from "../src/engine";
import { getFlowRedirect } from "../src/flow";
import { useSession } from "../src/session";
import { useSkateSession } from "../src/skateSession/skateSessionContext";
import { C, F } from "../src/theme";
import { Btn, Eyebrow } from "../src/ui";

function resolveMimeType(asset: ImagePicker.ImagePickerAsset): string {
  if (asset.mimeType === "video/quicktime") return "video/quicktime";
  return "video/mp4";
}

class QuotaExceededError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "QuotaExceededError";
  }
}

export default function Capture() {
  const router = useRouter();
  const { user } = useAccount();
  const { trick, analysis, selectedTrick, setAnalysis, setPendingClipJobId } = useSession();
  const { activeSession, hasActiveSession } = useSkateSession();
  const insets = useSafeAreaInsets();
  const [busy, setBusy] = useState(false);
  const [statusLabel, setStatusLabel] = useState<string | null>(null);

  const redirect = getFlowRedirect("capture", { trick, analysis });
  if (redirect) return <Redirect href={redirect} />;

  const calledTrick = trick!;
  const canUploadToSession = hasActiveSession && Boolean(activeSession?.id) && Boolean(user?.user_id);

  const showPermissionAlert = (canAskAgain: boolean) => {
    Alert.alert(
      "Camera access needed",
      canAskAgain
        ? "Allow camera access to film a skate clip."
        : "Camera access is disabled. Open system settings to enable it for OnFlow Lite.",
      canAskAgain
        ? [{ text: "OK" }]
        : [
            { text: "Cancel", style: "cancel" },
            { text: "Open settings", onPress: () => void Linking.openSettings() },
          ],
    );
  };

  const discardPendingJob = async (userId: string) => {
    const result = await clearPendingAnalysisJob(userId);
    if (!result.ok) {
      Alert.alert("Couldn't discard analysis", result.error);
      return;
    }
    setPendingClipJobId(null);
    setAnalysis(null);
  };

  const uploadUserClip = async (asset: ImagePicker.ImagePickerAsset, called: string) => {
    if (!activeSession?.id || !user?.user_id) {
      throw new Error("No signed-in active session is available for this upload.");
    }

    const userId = user.user_id;
    const sessionId = activeSession.id;
    const fileInfo = await FileSystem.getInfoAsync(asset.uri, { size: true });
    if (!fileInfo.exists || typeof fileInfo.size !== "number" || fileInfo.size <= 0) {
      throw new Error("Could not read the video file size.");
    }
    if (typeof asset.duration !== "number" || asset.duration <= 0) {
      throw new Error("Could not read the video duration. Choose a different clip.");
    }
    if (
      typeof asset.width !== "number" ||
      asset.width <= 0 ||
      typeof asset.height !== "number" ||
      asset.height <= 0
    ) {
      throw new Error("Could not read the video dimensions. Choose a different clip.");
    }

    let recoveryJobId: string | null = null;
    const durationSec = asset.duration / 1000;
    setStatusLabel("Preparing upload…");
    const uploaded = await uploadClipToSession({
      sessionId,
      fileUri: asset.uri,
      mimeType: resolveMimeType(asset),
      durationSeconds: durationSec,
      widthPx: asset.width,
      heightPx: asset.height,
      sizeBytes: fileInfo.size,
      clientHintTrickId: selectedTrick?.trickId ?? null,
      onInitiated: async (initiated) => {
        const pendingResult = await savePendingAnalysisJob(userId, {
          jobId: initiated.clip_id,
          sessionId,
          trickName: called,
          selectedTrick,
          submittedAt: new Date().toISOString(),
        });
        if (!pendingResult.ok) {
          throw new Error(`Could not save analysis recovery data: ${pendingResult.error}`);
        }
        recoveryJobId = initiated.clip_id;
        setAnalysis(null);
        setPendingClipJobId(initiated.clip_id);
      },
      onProgress: (fraction) => {
        setStatusLabel(`Uploading clip… ${Math.round(fraction * 100)}%`);
      },
    });

    if (!uploaded.ok) {
      if (isQuotaExceededMessage(uploaded.error.message)) {
        throw new QuotaExceededError(uploaded.error.message);
      }
      if (recoveryJobId) {
        track("capture_interrupted", {
          source: "user_upload",
          trick: called,
          job_id: recoveryJobId,
          message: uploaded.error.message,
        });
        Alert.alert(
          "Upload interrupted",
          `${uploaded.error.message}\n\nThe job ID was saved. You can check whether the server received it or discard it and try again.`,
          [
            {
              text: "Discard",
              style: "destructive",
              onPress: () => void discardPendingJob(userId),
            },
            { text: "Check status", onPress: () => router.replace("/analyzing") },
          ],
        );
        return;
      }
      throw new Error(uploaded.error.message);
    }

    track("capture_completed", { source: "user_upload", trick: called, job_id: uploaded.data });
    router.push("/analyzing");
  };

  const runUserClipLocal = (asset: ImagePicker.ImagePickerAsset, called: string) => {
    const durationSec = typeof asset.duration === "number" ? asset.duration / 1000 : null;
    setPendingClipJobId(null);
    setAnalysis(analyzeUserClip(asset.uri, durationSec, called));
    track("capture_completed", { source: "user", trick: called });
    router.push("/analyzing");
  };

  const runUserClip = async (fromCamera: boolean) => {
    if (busy) return;
    setBusy(true);
    setStatusLabel(null);

    try {
      if (fromCamera) {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!permission.granted) {
          showPermissionAlert(permission.canAskAgain);
          return;
        }
      }

      const launchPicker = fromCamera
        ? ImagePicker.launchCameraAsync
        : ImagePicker.launchImageLibraryAsync;
      const result = await launchPicker({
        mediaTypes: ["videos"],
        videoMaxDuration: 15,
        quality: 1,
      });

      if (result.canceled) return;

      const asset = result.assets?.[0];
      if (!asset || asset.type !== "video") {
        Alert.alert("Video not available", "Choose or record a video clip and try again.");
        return;
      }

      if (canUploadToSession) {
        await uploadUserClip(asset, calledTrick);
      } else {
        runUserClipLocal(asset, calledTrick);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown capture error";
      track("capture_failed", { source: fromCamera ? "camera" : "library", message });
      if (error instanceof QuotaExceededError) {
        Alert.alert("Analysis limit reached", message, [
          { text: "Not now", style: "cancel" },
          { text: "View upgrade", onPress: () => router.push(PAYWALL_ROUTE) },
        ]);
        return;
      }
      Alert.alert("Couldn't upload the clip", message);
    } finally {
      setBusy(false);
      setStatusLabel(null);
    }
  };

  const runSampleClip = (clip: (typeof SAMPLE_CLIPS)[number]) => {
    if (busy) return;
    setBusy(true);
    setPendingClipJobId(null);
    setAnalysis(analyzeSample(clip, calledTrick));
    track("capture_completed", { source: "sample", trick: calledTrick, clipId: clip.id });
    router.push("/analyzing");
  };

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <View style={{ gap: 4 }}>
        <Eyebrow>STEP 2 · PICK A CLIP</Eyebrow>
        <Text style={s.called}>
          Called: <Text style={{ color: C.volt, fontFamily: F.bold }}>{calledTrick}</Text>
        </Text>
        {canUploadToSession ? (
          <Text style={s.modeHint}>Active session — your clip uploads for real analysis.</Text>
        ) : (
          <Text style={s.modeHint}>No active session — local self-report mode only.</Text>
        )}
        {statusLabel ? <Text style={s.status}>{statusLabel}</Text> : null}
      </View>

      <Eyebrow>SAMPLE CLIPS · SCRIPTED LITE ANALYSES</Eyebrow>
      {SAMPLE_CLIPS.map((clip) => (
        <Pressable
          key={clip.id}
          disabled={busy}
          style={({ pressed }) => [s.clipCard, { opacity: busy ? 0.5 : pressed ? 0.75 : 1 }]}
          onPress={() => runSampleClip(clip)}
        >
          <Text style={s.clipLabel}>{clip.label}</Text>
          <Text style={s.clipSpot}>
            {clip.spot} · {clip.durationSec}s
          </Text>
        </Pressable>
      ))}

      <Eyebrow>YOUR OWN FOOTAGE{canUploadToSession ? " · UPLOAD" : " · SELF-REPORT"}</Eyebrow>
      <View style={{ gap: 10 }}>
        <Btn label="Film with camera" onPress={() => void runUserClip(true)} disabled={busy} />
        <Btn
          label="Pick from library"
          variant="ghost"
          onPress={() => void runUserClip(false)}
          disabled={busy}
        />
      </View>

      <View style={{ marginTop: "auto" }}>
        <Btn label="Back" variant="ghost" onPress={() => router.back()} disabled={busy} />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24, gap: 12 },
  called: { fontFamily: F.body, fontSize: 13, color: C.offwhite },
  modeHint: { fontFamily: F.body, fontSize: 12, color: C.dim, marginTop: 2 },
  status: { fontFamily: F.mono, fontSize: 11, color: C.volt, marginTop: 4 },
  clipCard: {
    backgroundColor: C.charcoal2,
    borderWidth: 1,
    borderColor: C.aluminum,
    borderRadius: 10,
    padding: 16,
    gap: 2,
  },
  clipLabel: { fontFamily: F.bold, fontSize: 16, color: C.offwhite },
  clipSpot: { fontFamily: F.mono, fontSize: 11, color: C.dim },
});
