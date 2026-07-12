import React from "react";
import { Linking, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useAccount } from "../src/auth/accountContext";
import { isProTier, PAYWALL_ROUTE } from "../src/billing/quota";
import { DELETE_ACCOUNT_INFO_URL, PRIVACY_URL, TERMS_URL } from "../src/legal/urls";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow } from "../src/ui";

export default function SettingsScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAccount();

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
          label="Delete account info"
          variant="ghost"
          onPress={() => void Linking.openURL(DELETE_ACCOUNT_INFO_URL)}
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
