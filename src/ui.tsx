import React from "react";
import { Pressable, Text, View, StyleSheet, ViewStyle } from "react-native";
import { C, F } from "./theme";
import { EvidenceTag } from "./types";

export function Eyebrow({ children, color = C.dim }: { children: React.ReactNode; color?: string }) {
  return <Text style={[s.eyebrow, { color }]}>{children}</Text>;
}

export function Card({
  children,
  accent,
  style,
}: {
  children: React.ReactNode;
  accent?: string;
  style?: ViewStyle;
}) {
  return (
    <View style={[s.card, accent ? { borderLeftWidth: 4, borderLeftColor: accent } : null, style]}>
      {children}
    </View>
  );
}

export function Tag({ kind }: { kind: EvidenceTag }) {
  const color = kind === "DETECTED" ? C.volt : kind === "ESTIMATE" ? C.amber : C.red;
  return (
    <View style={[s.tag, { borderColor: color }]}>
      <Text style={[s.tagText, { color }]}>{kind}</Text>
    </View>
  );
}

export function Btn({
  label,
  onPress,
  variant = "volt",
  disabled = false,
}: {
  label: string;
  onPress: () => void;
  variant?: "volt" | "ghost" | "red";
  disabled?: boolean;
}) {
  const bg = variant === "volt" ? C.volt : variant === "red" ? C.red : "transparent";
  const fg = variant === "volt" ? C.charcoal : C.offwhite;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        s.btn,
        { backgroundColor: bg, opacity: disabled ? 0.35 : pressed ? 0.75 : 1 },
        variant === "ghost" ? { borderWidth: 1, borderColor: C.aluminum } : null,
      ]}
    >
      <Text style={[s.btnText, { color: fg }]}>{label}</Text>
    </Pressable>
  );
}

export function LiteBanner() {
  return (
    <View style={s.liteBanner}>
      <Text style={s.liteBannerText}>
        LITE ENGINE — feedback below is generated sample data, not real video analysis.
      </Text>
    </View>
  );
}

const s = StyleSheet.create({
  eyebrow: { fontFamily: F.mono, fontSize: 11, letterSpacing: 1.4 },
  card: {
    backgroundColor: C.charcoal2,
    borderWidth: 1,
    borderColor: C.aluminum,
    borderRadius: 10,
    padding: 16,
    gap: 6,
  },
  tag: {
    borderWidth: 1,
    borderRadius: 3,
    paddingHorizontal: 6,
    paddingVertical: 2,
    alignSelf: "flex-start",
  },
  tagText: { fontFamily: F.mono, fontSize: 9, letterSpacing: 0.8 },
  btn: { borderRadius: 8, paddingVertical: 15, alignItems: "center" },
  btnText: { fontFamily: F.bold, fontSize: 15 },
  liteBanner: {
    backgroundColor: C.charcoal2,
    borderWidth: 1,
    borderColor: C.amber,
    borderRadius: 8,
    padding: 10,
  },
  liteBannerText: { fontFamily: F.mono, fontSize: 10, color: C.amber, lineHeight: 15 },
});
