import React, { useState } from "react";
import { View, Text, Pressable, StyleSheet, Alert, Linking } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as FileSystem from "expo-file-system";
import * as ImagePicker from "expo-image-picker";
import { track } from "../src/analytics";
import { uploadClipToSession } from "../src/api/clipApi";
import { C, F } from "../src/theme";
import { Btn, Eyebrow } from "../src/ui";
import { SAMPLE_CLIPS, analyzeSample, analyzeUserClip } from "../src/engine";
import { getFlowRedirect } from "../src/flow";
import { useSkateSession } from "../src/skateSession/skateSessionContext";
import { useSession } from "../src/session";

function resolveMimeType(asset: ImagePicker.ImagePickerAsset): string {
  if (asset.mimeType === "video/quicktime") return "video/quicktime";
  return "video/mp4";
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

  const uploadUserClip = async (asset: ImagePicker.ImagePickerAsset, called: string) => {
    if (!activeSession?.id) {
      throw new Error("No active session to upload into.");
    }

    const fileInfo = await FileSystem.getInfoAsync(asset.uri);
    if (!fileInfo.exists || typeof fileInfo.size !== "number" || fileInfo.size <= 0) {
      throw new Error("Could not read the video file size.");
    }

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
      throw new Error(uploaded.error.message);
    }

    setAnalysis(null);
    setPendingClipJobId(uploaded.data);
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
