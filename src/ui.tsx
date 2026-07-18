import React from "react";
import {
  Pressable,
  Text,
  View,
  StyleSheet,
  ViewStyle,
  TextInput,
  TextInputProps,
} from "react-native";
import { DaySlot } from "./progress";
import { C, F } from "./theme";
import { EvidenceClass, EvidenceTag } from "./types";

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

export function Tag({ kind }: { kind: EvidenceTag | EvidenceClass }) {
  const color = kind === "DETECTED" ? C.volt : kind === "ESTIMATE" ? C.amber : C.red;
  return (
    <View style={[s.tag, { borderColor: color }]}>
      <Text style={[s.tagText, { color }]}>{kind}</Text>
    </View>
  );
}

export function Field({
  label,
  ...props
}: { label: string } & TextInputProps) {
  return (
    <View style={s.field}>
      <Text style={s.fieldLabel}>{label}</Text>
      <TextInput
        placeholderTextColor={C.dim}
        style={s.fieldInput}
        {...props}
      />
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
  const bg = variant === "volt" ? C.volt : variant === "red" ? C.red : C.charcoal2;
  const fg = variant === "volt" ? C.charcoal : C.offwhite;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        s.btn,
        { backgroundColor: bg, opacity: disabled ? 0.35 : pressed ? 0.78 : 1 },
        variant === "ghost" ? s.ghostBtn : null,
      ]}
    >
      <Text style={[s.btnText, { color: fg }]}>{label}</Text>
    </Pressable>
  );
}

export function LiteBanner({ message }: { message?: string }) {
  return (
    <View style={s.liteBanner}>
      <Text style={s.liteBannerText}>
        {message ??
          "LITE ENGINE — feedback below is generated sample data, not real video analysis."}
      </Text>
    </View>
  );
}

export function StorageWarningBanner({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss: () => void;
}) {
  return (
    <Pressable style={s.storageWarning} onPress={onDismiss}>
      <Text style={s.storageWarningText}>{message}</Text>
      <Text style={s.storageWarningDismiss}>Tap to dismiss</Text>
    </Pressable>
  );
}

export function WeekRow({ days }: { days: DaySlot[] }) {
  return (
    <View style={s.weekRow}>
      {days.map((d) => (
        <View key={d.date} style={s.weekCell}>
          <View
            style={[
              s.weekDot,
              d.status === "landed"
                ? { backgroundColor: C.volt }
                : d.status === "bailed"
                  ? { backgroundColor: C.red }
                  : { backgroundColor: C.charcoal3, borderWidth: 1, borderColor: C.dim },
            ]}
          />
          <Text style={s.weekLabel}>{d.label}</Text>
        </View>
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  eyebrow: { fontFamily: F.mono, fontSize: 11, letterSpacing: 1.4 },
  card: {
    backgroundColor: C.charcoal2,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.charcoal3,
    borderRadius: 12,
    padding: 16,
    gap: 6,
  },
  tag: {
    borderWidth: 1,
    borderRadius: 4,
    paddingHorizontal: 7,
    paddingVertical: 3,
    alignSelf: "flex-start",
  },
  tagText: { fontFamily: F.mono, fontSize: 9, letterSpacing: 0.8 },
  btn: {
    minHeight: 52,
    borderRadius: 12,
    paddingHorizontal: 18,
    paddingVertical: 15,
    alignItems: "center",
    justifyContent: "center",
  },
  ghostBtn: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.charcoal3,
  },
  btnText: { fontFamily: F.bold, fontSize: 15 },
  liteBanner: {
    backgroundColor: C.charcoal2,
    borderLeftWidth: 3,
    borderLeftColor: C.amber,
    borderRadius: 8,
    padding: 10,
  },
  liteBannerText: { fontFamily: F.mono, fontSize: 10, color: C.amber, lineHeight: 15 },
  storageWarning: {
    backgroundColor: C.charcoal2,
    borderLeftWidth: 3,
    borderLeftColor: C.red,
    borderRadius: 8,
    padding: 10,
    gap: 4,
  },
  storageWarningText: { fontFamily: F.mono, fontSize: 10, color: C.offwhite, lineHeight: 15 },
  storageWarningDismiss: { fontFamily: F.mono, fontSize: 9, color: C.dim },
  weekRow: { flexDirection: "row", justifyContent: "space-between", gap: 4 },
  weekCell: { alignItems: "center", gap: 6, flex: 1 },
  weekDot: { width: 14, height: 14, borderRadius: 7 },
  weekLabel: { fontFamily: F.mono, fontSize: 9, color: C.dim },
  field: { gap: 6 },
  fieldLabel: { fontFamily: F.mono, fontSize: 10, color: C.dim, letterSpacing: 0.8 },
  fieldInput: {
    fontFamily: F.body,
    fontSize: 14,
    color: C.offwhite,
    backgroundColor: C.charcoal2,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.charcoal3,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 11,
  },
});
