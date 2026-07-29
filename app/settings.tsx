import React, { useState } from "react";
import { Alert, Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useAccount } from "../src/auth/accountContext";
import { useAuth } from "../src/auth/authContext";
import { isProTier, PAYWALL_ROUTE } from "../src/billing/quota";
import { DELETE_ACCOUNT_INFO_URL, PRIVACY_URL, TERMS_URL } from "../src/legal/urls";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow } from "../src/ui";

function Row({ label, value, onPress, danger = false }: { label: string; value?: string; onPress: () => void; danger?: boolean }) {
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
  const [signingOut, setSigningOut] = useState(false);

  const handleSignOut = async () => {
    if (signingOut) return;
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

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}> 
      <View style={{ gap: 6 }}><Eyebrow color={C.red}>ONFLOW</Eyebrow><Text style={s.title}>Settings</Text></View>

      {user ? (
        <Card accent={C.volt}>
          <Eyebrow color={C.volt}>ACCOUNT</Eyebrow>
          <Text style={s.value}>{user.email || user.user_id}</Text>
          <Text style={s.meta}>{String(user.tier).toUpperCase()} PLAN</Text>
        </Card>
      ) : null}

      {!isProTier(user?.tier) ? <Btn label="Upgrade to Pro" onPress={() => router.push(PAYWALL_ROUTE)} /> : null}

      <View style={s.group}>
        <Row label="Notifications" onPress={() => router.push("/notifications" as never)} />
        <Row label="Terms of Service" onPress={() => void Linking.openURL(TERMS_URL)} />
        <Row label="Privacy Policy" onPress={() => void Linking.openURL(PRIVACY_URL)} />
        <Row label="Delete account information" onPress={() => void Linking.openURL(DELETE_ACCOUNT_INFO_URL)} danger />
      </View>

      <View style={{ marginTop: "auto", gap: 10 }}>
        <Btn label={signingOut ? "Signing out…" : "Sign out"} variant="red" onPress={() => void handleSignOut()} disabled={signingOut} />
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
  row: { minHeight: 58, paddingHorizontal: 16, flexDirection: "row", alignItems: "center", borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.charcoal3 },
  rowLabel: { fontFamily: F.bold, fontSize: 14, color: C.offwhite },
  rowValue: { fontFamily: F.body, fontSize: 11, color: C.dim, marginTop: 2 },
  chevron: { fontFamily: F.body, fontSize: 24, color: C.dim },
});
