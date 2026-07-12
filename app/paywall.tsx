import React, { useEffect } from "react";
import { Linking, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { useAccount } from "../src/auth/accountContext";
import { isProTier } from "../src/billing/quota";
import { PRIVACY_URL, TERMS_URL } from "../src/legal/urls";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow } from "../src/ui";

export default function PaywallScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAccount();
  const isPro = isProTier(user?.tier);

  useEffect(() => {
    track("paywall_viewed", { tier: user?.tier ?? "unknown" });
  }, [user?.tier]);

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <View style={{ gap: 6 }}>
        <Eyebrow>ONFLOW PRO</Eyebrow>
        <Text style={s.title}>{isPro ? "You're on Pro" : "Upgrade for more analyses"}</Text>
        <Text style={s.sub}>
          {isPro
            ? "Unlimited clip analyses are active on your account."
            : "You've hit the free analysis limit. Pro unlocks unlimited uploads and priority processing."}
        </Text>
      </View>

      <Card accent={C.volt}>
        <Eyebrow color={C.volt}>CURRENT PLAN</Eyebrow>
        <Text style={s.plan}>{user?.tier ?? "free"}</Text>
        {user?.bonus_analyses_remaining != null && user.bonus_analyses_remaining > 0 ? (
          <Text style={s.meta}>Bonus analyses remaining: {user.bonus_analyses_remaining}</Text>
        ) : null}
      </Card>

      {!isPro ? (
        <Card>
          <Eyebrow>WHAT PRO INCLUDES</Eyebrow>
          <Text style={s.bullet}>· Unlimited clip analyses per month</Text>
          <Text style={s.bullet}>· Priority processing queue</Text>
          <Text style={s.bullet}>· Re-Up packs for extra credits (coming in lite)</Text>
        </Card>
      ) : null}

      <Text style={s.note}>
        In-app purchases are not wired in OnFlow Lite yet. Manage billing in the full OnFlow app or
        contact support if you need Pro access.
      </Text>

      <View style={{ gap: 10 }}>
        <Btn label="Terms of Service" variant="ghost" onPress={() => void Linking.openURL(TERMS_URL)} />
        <Btn label="Privacy Policy" variant="ghost" onPress={() => void Linking.openURL(PRIVACY_URL)} />
        <Btn label="Back" variant="ghost" onPress={() => router.back()} />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24, gap: 14 },
  title: { fontFamily: F.heading, fontSize: 24, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
  plan: { fontFamily: F.bold, fontSize: 18, color: C.volt, marginTop: 4, textTransform: "capitalize" },
  meta: { fontFamily: F.body, fontSize: 13, color: C.dim, marginTop: 4 },
  bullet: { fontFamily: F.body, fontSize: 13, color: C.offwhite, marginTop: 4 },
  note: { fontFamily: F.body, fontSize: 12, lineHeight: 18, color: C.dim },
});
