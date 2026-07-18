import React, { useCallback, useState } from "react";
import { Alert, Linking, Share, StyleSheet, Text, View } from "react-native";
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

export default function SettingsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAccount();
  const { signOut } = useAuth();
  const [busy, setBusy] = useState<"export" | "delete" | null>(null);

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
      router.replace("/sign-in");
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
        <Eyebrow>APP</Eyebrow>
        <Text style={s.title}>Settings</Text>
      </View>

      {user ? (
        <Card>
          <Eyebrow color={C.volt}>ACCOUNT</Eyebrow>
          <Text style={s.value}>{user.email || user.user_id}</Text>
          <Text style={s.meta}>Tier: {user.tier}</Text>
        </Card>
      ) : null}

      <View style={{ gap: 10 }}>
        <Btn label="Notifications" variant="ghost" onPress={() => router.push("/notifications")} />
        {!isProTier(user?.tier) ? (
          <Btn label="Upgrade to Pro" onPress={() => router.push(PAYWALL_ROUTE)} />
        ) : null}
        <Btn label="Terms of Service" variant="ghost" onPress={() => void Linking.openURL(TERMS_URL)} />
        <Btn label="Privacy Policy" variant="ghost" onPress={() => void Linking.openURL(PRIVACY_URL)} />
        <Btn
          label={busy === "export" ? "Exporting…" : "Export my data"}
          variant="ghost"
          onPress={() => void onExport()}
        />
        <Btn
          label="Delete account info"
          variant="ghost"
          onPress={() => void Linking.openURL(DELETE_ACCOUNT_INFO_URL)}
        />
        <Btn
          label={busy === "delete" ? "Deleting…" : "Delete my account"}
          variant="ghost"
          onPress={onDeletePress}
        />
        <Btn label="Back" variant="ghost" onPress={() => router.back()} />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24, gap: 14 },
  title: { fontFamily: F.heading, fontSize: 24, color: C.offwhite },
  value: { fontFamily: F.bold, fontSize: 15, color: C.offwhite, marginTop: 4 },
  meta: { fontFamily: F.body, fontSize: 13, color: C.dim, marginTop: 4 },
});
