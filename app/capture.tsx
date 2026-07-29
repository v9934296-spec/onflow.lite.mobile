import React, { useState } from "react";
import { Alert, Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as FileSystem from "expo-file-system";
import * as ImagePicker from "expo-image-picker";
import { track } from "../src/analytics";
import { uploadClipToSession } from "../src/api/clipApi";
import { isQuotaExceededMessage, PAYWALL_ROUTE } from "../src/billing/quota";
import { C, F } from "../src/theme";
import { Btn, Eyebrow } from "../src/ui";
import { SAMPLE_CLIPS, analyzeSample, analyzeUserClip } from "../src/engine";
import { getFlowRedirect } from "../src/flow";
import { useSkateSession } from "../src/skateSession/skateSessionContext";
import { useSession } from "../src/session";

function resolveMimeType(asset: ImagePicker.ImagePickerAsset): string {
  return asset.mimeType === "video/quicktime" ? "video/quicktime" : "video/mp4";
}

class QuotaExceededError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "QuotaExceededError";
  }
}

export default function Capture() {
  const router = useRouter();
  const { trick, analysis, selectedTrick, setAnalysis, setPendingClipJobId } = useSession();
  const { activeSession, hasActiveSession } = useSkateSession();
  const insets = useSafeAreaInsets();
  const [busy, setBusy] = useState(false);
  const [statusLabel, setStatusLabel] = useState<string | null>(null);

  const redirect = getFlowRedirect("capture", { trick, analysis });
  if (redirect) return <Redirect href={redirect} />;

  const calledTrick = trick!;
  const canUploadToSession = hasActiveSession && Boolean(activeSession?.id);

  const showPermissionAlert = (canAskAgain: boolean) => {
    Alert.alert(
      "Camera access needed",
      canAskAgain ? "Allow camera access to film a skate clip." : "Camera access is disabled. Open system settings to enable it for OnFlow.",
      canAskAgain ? [{ text: "OK" }] : [{ text: "Cancel", style: "cancel" }, { text: "Open settings", onPress: () => void Linking.openSettings() }],
    );
  };

  const uploadUserClip = async (asset: ImagePicker.ImagePickerAsset, called: string) => {
    if (!activeSession?.id) throw new Error("No active session to upload into.");
    const fileInfo = await FileSystem.getInfoAsync(asset.uri);
    if (!fileInfo.exists || typeof fileInfo.size !== "number" || fileInfo.size <= 0) throw new Error("Could not read the video file size.");

    const durationSec = typeof asset.duration === "number" ? asset.duration / 1000 : 2;
    const widthPx = typeof asset.width === "number" && asset.width > 0 ? asset.width : 1920;
    const heightPx = typeof asset.height === "number" && asset.height > 0 ? asset.height : 1080;

    setStatusLabel("Uploading clip…");
    const uploaded = await uploadClipToSession({
      sessionId: activeSession.id,
      fileUri: asset.uri,
      mimeType: resolveMimeType(asset),
      durationSeconds: durationSec,
      widthPx,
      heightPx,
      sizeBytes: fileInfo.size,
      clientHintTrickId: selectedTrick?.trickId ?? null,
    });
    if (!uploaded.ok) {
      if (isQuotaExceededMessage(uploaded.error.message)) throw new QuotaExceededError(uploaded.error.message);
      throw new Error(uploaded.error.message);
    }
    setAnalysis(null);
    setPendingClipJobId(uploaded.data);
    track("capture_completed", { source: "user_upload", trick: called, job_id: uploaded.data });
    router.push("/analyzing" as never);
  };

  const runUserClipLocal = (asset: ImagePicker.ImagePickerAsset, called: string) => {
    const durationSec = typeof asset.duration === "number" ? asset.duration / 1000 : null;
    setPendingClipJobId(null);
    setAnalysis(analyzeUserClip(asset.uri, durationSec, called));
    track("capture_completed", { source: "user", trick: called });
    router.push("/analyzing" as never);
  };

  const runUserClip = async (fromCamera: boolean) => {
    if (busy) return;
    setBusy(true);
    setStatusLabel(null);
    try {
      if (fromCamera) {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!permission.granted) { showPermissionAlert(permission.canAskAgain); return; }
      }
      const launchPicker = fromCamera ? ImagePicker.launchCameraAsync : ImagePicker.launchImageLibraryAsync;
      const result = await launchPicker({ mediaTypes: ["videos"], videoMaxDuration: 15, quality: 1 });
      if (result.canceled) return;
      const asset = result.assets?.[0];
      if (!asset || asset.type !== "video") { Alert.alert("Video not available", "Choose or record a video clip and try again."); return; }
      if (canUploadToSession) await uploadUserClip(asset, calledTrick); else runUserClipLocal(asset, calledTrick);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown capture error";
      track("capture_failed", { source: fromCamera ? "camera" : "library", message });
      if (error instanceof QuotaExceededError) {
        Alert.alert("Analysis limit reached", message, [{ text: "Not now", style: "cancel" }, { text: "View upgrade", onPress: () => router.push(PAYWALL_ROUTE) }]);
      } else {
        Alert.alert("Couldn't upload the clip", message);
      }
    } finally {
      setBusy(false);
      setStatusLabel(null);
    }
  };

  const runDevSample = () => {
    const clip = SAMPLE_CLIPS[0];
    if (!clip || busy) return;
    setPendingClipJobId(null);
    setAnalysis(analyzeSample(clip, calledTrick));
    router.push("/analyzing" as never);
  };

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}> 
      <View style={s.header}>
        <Eyebrow color={C.red}>FILM ATTEMPT</Eyebrow>
        <Text style={s.title}>{calledTrick}</Text>
        <Text style={s.sub}>Keep the skater and board visible from setup through roll-away. Better evidence means better feedback.</Text>
        {statusLabel ? <Text style={s.status}>{statusLabel}</Text> : null}
      </View>

      <Pressable disabled={busy} onPress={() => void runUserClip(true)} style={({ pressed }) => [s.cameraCard, (pressed || busy) && s.pressed]}>
        <Eyebrow color={C.charcoal}>CAMERA</Eyebrow>
        <Text style={s.cameraTitle}>Film it now.</Text>
        <Text style={s.cameraCopy}>Record up to 15 seconds and send the clip straight into analysis.</Text>
        <Text style={s.cameraAction}>OPEN CAMERA →</Text>
      </Pressable>

      <Pressable disabled={busy} onPress={() => void runUserClip(false)} style={({ pressed }) => [s.libraryCard, (pressed || busy) && s.pressed]}>
        <Eyebrow color={C.red}>LIBRARY</Eyebrow>
        <Text style={s.libraryTitle}>Use an existing clip.</Text>
        <Text style={s.sub}>Pick footage you already filmed. The same evidence rules apply.</Text>
      </Pressable>

      <View style={s.truthBox}>
        <Eyebrow>HONEST ANALYSIS</Eyebrow>
        <Text style={s.truth}>If the footage cannot support a claim, OnFlow should say that instead of manufacturing precision.</Text>
      </View>

      {typeof __DEV__ !== "undefined" && __DEV__ ? (
        <Btn label="Developer sample analysis" variant="ghost" onPress={runDevSample} disabled={busy} />
      ) : null}

      <View style={{ marginTop: "auto" }}><Btn label="Back to Flow" variant="ghost" onPress={() => router.replace("/flow" as never)} disabled={busy} /></View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24, gap: 14 },
  header: { gap: 7 },
  title: { fontFamily: F.heading, fontSize: 32, lineHeight: 36, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
  status: { fontFamily: F.mono, fontSize: 11, color: C.volt },
  cameraCard: { borderRadius: 16, padding: 20, gap: 8, backgroundColor: C.volt },
  cameraTitle: { fontFamily: F.heading, fontSize: 26, color: C.charcoal },
  cameraCopy: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.charcoal },
  cameraAction: { fontFamily: F.bold, fontSize: 13, color: C.charcoal, marginTop: 4 },
  libraryCard: { borderRadius: 16, padding: 20, gap: 8, backgroundColor: C.charcoal2, borderLeftWidth: 4, borderLeftColor: C.red },
  libraryTitle: { fontFamily: F.heading, fontSize: 22, color: C.offwhite },
  truthBox: { gap: 6, paddingVertical: 8 },
  truth: { fontFamily: F.body, fontSize: 12, lineHeight: 18, color: C.dim },
  pressed: { opacity: 0.7 },
});
