import React, { useState } from "react";
import { View, Text, Pressable, StyleSheet, Alert, Linking } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as ImagePicker from "expo-image-picker";
import { track } from "../src/analytics";
import { C, F } from "../src/theme";
import { Btn, Eyebrow } from "../src/ui";
import { SAMPLE_CLIPS, analyzeSample, analyzeUserClip } from "../src/engine";
import { getFlowRedirect } from "../src/flow";
import { useSession } from "../src/session";

export default function Capture() {
  const router = useRouter();
  const { trick, analysis, setAnalysis } = useSession();
  const insets = useSafeAreaInsets();
  const [busy, setBusy] = useState(false);

  const redirect = getFlowRedirect("capture", { trick, analysis });
  if (redirect) return <Redirect href={redirect} />;

  const calledTrick = trick;

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

  const runUserClip = async (fromCamera: boolean) => {
    if (busy) return;
    setBusy(true);

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

      const durationSec = typeof asset.duration === "number" ? asset.duration / 1000 : null;
      setAnalysis(analyzeUserClip(asset.uri, durationSec, calledTrick));
      track("capture_completed", { source: "user", trick: calledTrick });
      router.push("/analyzing");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown capture error";
      track("capture_failed", { source: fromCamera ? "camera" : "library", message });
      Alert.alert("Couldn't open the clip", "Nothing was logged. Try the camera or library again.");
    } finally {
      setBusy(false);
    }
  };

  const runSampleClip = (clip: (typeof SAMPLE_CLIPS)[number]) => {
    if (busy) return;
    setBusy(true);
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

      <Eyebrow>YOUR OWN FOOTAGE · SELF-REPORT · ESTIMATE ONLY</Eyebrow>
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
