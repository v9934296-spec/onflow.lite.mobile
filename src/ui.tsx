import React from "react";
import {
  Pressable,
  Text,
  View,
  StyleSheet,
  ViewStyle,
  TextInput,
  TextInputProps,
  ActivityIndicator,
} from "react-native";
import { DaySlot } from "./progress";
import { C, F, RADIUS, SPACE, withOpacity } from "./theme";
import { EvidenceClass, EvidenceTag } from "./types";

export function Eyebrow({ children, color = C.dim }: { children: React.ReactNode; color?: string }) {
  return <Text style={[s.eyebrow, { color }]}>{children}</Text>;
}

export function Card({
  children,
  accent,
  style,
  onPress,
}: {
  children: React.ReactNode;
  accent?: string;
  style?: ViewStyle;
  onPress?: () => void;
}) {
  const body = (
    <View style={[s.card, style]}>
      {accent ? <View style={[s.edgeAccent, { backgroundColor: accent }]} /> : null}
      {children}
    </View>
  );
  if (!onPress) return body;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [{ opacity: pressed ? 0.92 : 1 }]}>
      {body}
    </Pressable>
  );
}

export function Tag({ kind }: { kind: EvidenceTag | EvidenceClass }) {
  const color = kind === "DETECTED" ? C.volt : kind === "ESTIMATE" ? C.amber : C.red;
  return (
    <View style={[s.tag, { borderColor: color, backgroundColor: withOpacity(color, 0.12) }]}>
      <Text style={[s.tagText, { color }]}>{kind}</Text>
    </View>
  );
}

export function Field({ label, ...props }: { label: string } & TextInputProps) {
  return (
    <View style={s.field}>
      <Text style={s.fieldLabel}>{label}</Text>
      <TextInput placeholderTextColor={C.dim} style={s.fieldInput} {...props} />
    </View>
  );
}

export function Btn({
  label,
  onPress,
  variant = "volt",
  disabled = false,
  loading = false,
}: {
  label: string;
  onPress: () => void;
  variant?: "volt" | "ghost" | "red" | "surface";
  disabled?: boolean;
  loading?: boolean;
}) {
  const isDisabled = disabled || loading;
  const bg =
    variant === "volt"
      ? C.volt
      : variant === "red"
        ? C.red
        : variant === "surface"
          ? C.charcoal3
          : "transparent";
  const fg = variant === "volt" ? C.charcoal : C.offwhite;
  const border =
    variant === "ghost"
      ? { borderWidth: StyleSheet.hairlineWidth, borderColor: C.charcoal4 }
      : variant === "surface"
        ? { borderWidth: 1, borderColor: C.charcoal4 }
        : null;

  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      style={({ pressed }) => [
        s.btn,
        { backgroundColor: bg, opacity: isDisabled ? 0.35 : pressed ? 0.78 : 1 },
        border,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <Text style={[s.btnText, { color: fg }]}>{label}</Text>
      )}
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

export function SkeletonLines({
  widths = ["60%", "85%", "45%"],
  testID,
}: {
  widths?: Array<`${number}%` | number>;
  testID?: string;
}) {
  return (
    <View testID={testID} style={{ gap: SPACE.sm, minHeight: 72 }}>
      {widths.map((width, index) => (
        <View
          key={`${testID ?? "skel"}-${index}`}
          style={{
            width,
            height: index === 0 ? 20 : 16,
            borderRadius: RADIUS.sm,
            backgroundColor: C.charcoal3,
          }}
        />
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  eyebrow: {
    fontFamily: F.mono,
    fontSize: 11,
    letterSpacing: 1.4,
    textTransform: "uppercase",
  },
  card: {
    backgroundColor: C.charcoal2,
    borderRadius: RADIUS.lg,
    padding: SPACE.lg,
    gap: SPACE.sm,
    overflow: "hidden",
    position: "relative",
    shadowColor: "#000",
    shadowOpacity: 0.25,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
  edgeAccent: {
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    width: 3,
    borderTopLeftRadius: RADIUS.lg,
    borderBottomLeftRadius: RADIUS.lg,
  },
  tag: {
    borderWidth: 1,
    borderRadius: RADIUS.sm,
    paddingHorizontal: 7,
    paddingVertical: 3,
    alignSelf: "flex-start",
  },
  tagText: { fontFamily: F.mono, fontSize: 9, letterSpacing: 0.8 },
  btn: {
    minHeight: 52,
    borderRadius: RADIUS.lg,
    paddingHorizontal: 18,
    paddingVertical: 15,
    alignItems: "center",
    justifyContent: "center",
  },
  btnText: { fontFamily: F.bold, fontSize: 15, textTransform: "uppercase", letterSpacing: 0.4 },
  liteBanner: {
    backgroundColor: C.charcoal2,
    borderLeftWidth: 3,
    borderLeftColor: C.amber,
    borderRadius: RADIUS.md,
    padding: 10,
  },
  liteBannerText: { fontFamily: F.mono, fontSize: 10, color: C.amber, lineHeight: 15 },
  storageWarning: {
    backgroundColor: C.charcoal2,
    borderLeftWidth: 3,
    borderLeftColor: C.red,
    borderRadius: RADIUS.md,
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
    borderColor: C.charcoal4,
    borderRadius: RADIUS.md,
    paddingHorizontal: 12,
    paddingVertical: 11,
  },
});
