import React, { useState } from "react";
import { View, Text, Pressable, StyleSheet, Alert } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as ImagePicker from "expo-image-picker";
import { C, F } from "../src/theme";
import { Btn, Eyebrow } from "../src/ui";
import { SAMPLE_CLIPS, analyzeSample, analyzeUserClip } from "../src/engine";
import { useSession } from "../src/session";

export default function Capture() {
  const router = useRouter();
  const { trick, setAnalysis } = useSession();
  const insets = useSafeAreaInsets();
  const [busy, setBusy] = useState(false);

  if (!trick) {
    // Loop entered out of order — send back to step 1
    router.replace("/trick");
    return null;
  }

  const runUserClip = async (fromCamera: boolean) => {
    setBusy(true);
    try {
      if (fromCamera) {
        const perm = await ImagePicker.requestCameraPermissionsAsync();
        if (!perm.granted) {
          Alert.alert("Camera needed", "Allow camera access to film a clip.");
          return;
        }
      }
      const fn = fromCamera ? ImagePicker.launchCameraAsync : ImagePicker.launchImageLibraryAsync;
      const result = await fn({
        mediaTypes: ["videos"],
        videoMaxDuration: 15,
        quality: 1,
      });
      if (result.canceled || !result.assets?.[0]) return;
      const asset = result.assets[0];
      const durationSec = asset.duration ? asset.duration / 1000 : null;
      setAnalysis(analyzeUserClip(asset.uri, durationSec, trick));
      router.push("/analyzing");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <View style={{ gap: 4 }}>
        <Eyebrow>STEP 2 · PICK A CLIP</Eyebrow>
        <Text style={s.called}>
          Called: <Text style={{ color: C.volt, fontFamily: F.bold }}>{trick}</Text>
        </Text>
      </View>

      <Eyebrow>SAMPLE CLIPS · SCRIPTED LITE ANALYSES</Eyebrow>
      {SAMPLE_CLIPS.map((clip) => (
        <Pressable
          key={clip.id}
          style={({ pressed }) => [s.clipCard, { opacity: pressed ? 0.75 : 1 }]}
          onPress={() => {
            setAnalysis(analyzeSample(clip, trick));
            router.push("/analyzing");
          }}
        >
          <Text style={s.clipLabel}>{clip.label}</Text>
          <Text style={s.clipSpot}>
            {clip.spot} · {clip.durationSec}s
          </Text>
        </Pressable>
      ))}

      <Eyebrow>YOUR OWN FOOTAGE · LITE READ (ESTIMATES ONLY)</Eyebrow>
      <View style={{ gap: 10 }}>
        <Btn label="Film with camera" onPress={() => runUserClip(true)} disabled={busy} />
        <Btn label="Pick from library" variant="ghost" onPress={() => runUserClip(false)} disabled={busy} />
      </View>

      <View style={{ marginTop: "auto" }}>
        <Btn label="Back" variant="ghost" onPress={() => router.back()} />
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
