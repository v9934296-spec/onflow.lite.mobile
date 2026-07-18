import React, { useCallback, useState } from "react";
import { Alert, Linking, Pressable, Share, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { deleteMyAccount, exportMyData } from "../src/api/accountApi";
import { useAccount } from "../src/auth/accountContext";
import { useAuth } from "../src/auth/authContext";
import { isProTier, PAYWALL_ROUTE } from "../src/billing/quota";
import { DELETE_ACCOUNT_INFO_URL, PRIVACY_URL, TERMS_URL } from "../src/legal/urls";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow } from "../src/ui";

function Row({
  label,
  value,
  onPress,
  danger = false,
}: {
  label: string;
  value?: string;
  onPress: () => void;
  danger?: boolean;
}) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [s.row, pressed && { opacity: 0.65 }]}>
      <View style={{ flex: 1 }}>
        <Text style={[s.rowLabel, danger && { color: C.red }]}>{label}</Text>
        {value ? <Text style={s.rowValue}>{value}</Text> : null}
      </View>
      <Text style={[s.chevron, danger && { color: C.red }]}>›</Text>
    </Pressable>
  );
}

export default function SettingsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAccount();
  const { signOut } = useAuth();
  const [busy, setBusy] = useState<"export" | "delete" | null>(null);
  const [signingOut, setSigningOut] = useState(false);

  const handleSignOut = async () => {
    if (signingOut || busy) return;
    setSigningOut(true);
    try {
      await signOut();
    } catch (error) {
      Alert.alert(
        "Couldn't sign out securely",
        error instanceof Error
          ? error.message
          : "The encrypted credential could not be removed. Restart the app and try again.",
      );
    } finally {
      setSigningOut(false);
    }
  };

  const onExport = useCallback(async () => {
    if (busy) return;
    setBusy("export");
    track("account_export_requested");
    try {
      const result = await exportMyData();
      if (!result.ok) {
        Alert.alert("Export failed", result.error.message);
        return;
      }
      const payload = JSON.stringify(result.data, null, 2);
      await Share.share({
        title: "OnFlow data export",
        message: payload,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Could not share export.";
      Alert.alert("Export failed", msg);
    } finally {
      setBusy(null);
    }
  }, [busy]);

  const runDelete = useCallback(async () => {
    if (busy) return;
    setBusy("delete");
    track("account_delete_requested");
    try {
      const result = await deleteMyAccount();
      if (!result.ok) {
        Alert.alert("Deletion failed", result.error.message);
        return;
      }
      await signOut();
      Alert.alert(
        "Account deletion queued",
        result.data.message ||
          "Your account is being deleted. Clips will be permanently removed shortly.",
      );
      router.replace("/sign-in" as never);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Could not delete account.";
      Alert.alert("Deletion failed", msg);
    } finally {
      setBusy(null);
    }
  }, [busy, router, signOut]);

  const onDeletePress = useCallback(() => {
    if (busy) return;
    Alert.alert(
      "Delete account?",
      "This permanently deletes your account, sessions, and clips. This cannot be undone.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete my account",
          style: "destructive",
          onPress: () => {
            void runDelete();
          },
        },
      ],
    );
  }, [busy, runDelete]);

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <View style={{ gap: 6 }}>
        <Eyebrow color={C.red}>ONFLOW</Eyebrow>
        <Text style={s.title}>Settings</Text>
      </View>

      {user ? (
        <Card accent={C.volt}>
          <Eyebrow color={C.volt}>ACCOUNT</Eyebrow>
          <Text style={s.value}>{user.email || user.user_id}</Text>
          <Text style={s.meta}>{String(user.tier).toUpperCase()} PLAN</Text>
        </Card>
      ) : null}

      {!isProTier(user?.tier) ? (
        <Btn label="Upgrade to Pro" onPress={() => router.push(PAYWALL_ROUTE)} />
      ) : null}

      <View style={s.group}>
        <Row label="Notifications" onPress={() => router.push("/notifications" as never)} />
        <Row label="Terms of Service" onPress={() => void Linking.openURL(TERMS_URL)} />
        <Row label="Privacy Policy" onPress={() => void Linking.openURL(PRIVACY_URL)} />
        <Row
          label={busy === "export" ? "Exporting…" : "Export my data"}
          onPress={() => void onExport()}
        />
        <Row
          label="Delete account information"
          onPress={() => void Linking.openURL(DELETE_ACCOUNT_INFO_URL)}
          danger
        />
        <Row
          label={busy === "delete" ? "Deleting…" : "Delete my account"}
          onPress={onDeletePress}
          danger
        />
      </View>

      <View style={{ marginTop: "auto", gap: 10 }}>
        <Btn
          label={signingOut ? "Signing out…" : "Sign out"}
          variant="red"
          onPress={() => void handleSignOut()}
          disabled={signingOut || Boolean(busy)}
        />
        <Btn label="Back" variant="ghost" onPress={() => router.back()} disabled={signingOut} />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24, gap: 16 },
  title: { fontFamily: F.heading, fontSize: 32, color: C.offwhite },
  value: { fontFamily: F.bold, fontSize: 15, color: C.offwhite, marginTop: 4 },
  meta: { fontFamily: F.mono, fontSize: 9, letterSpacing: 0.8, color: C.dim, marginTop: 4 },
  group: { backgroundColor: C.charcoal2, borderRadius: 14, overflow: "hidden" },
  row: {
    minHeight: 58,
    paddingHorizontal: 16,
    flexDirection: "row",
    alignItems: "center",
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.charcoal3,
  },
  rowLabel: { fontFamily: F.bold, fontSize: 14, color: C.offwhite },
  rowValue: { fontFamily: F.body, fontSize: 11, color: C.dim, marginTop: 2 },
  chevron: { fontFamily: F.body, fontSize: 24, color: C.dim },
});
