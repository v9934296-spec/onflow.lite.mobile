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

/**
 * Free-tier limit screen. OnFlow Lite does not ship in-app purchases yet —
 * copy must not imply a working store checkout path.
 */
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
        <Eyebrow>ANALYSIS LIMIT</Eyebrow>
        <Text style={s.title}>
          {isPro ? "You're on Pro" : "You've used this month's free analyses"}
        </Text>
        <Text style={s.sub}>
          {isPro
            ? "Unlimited clip analyses are active on your account."
            : "OnFlow Lite includes a free monthly analysis allowance. In-app purchases are not available in this build."}
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
          <Eyebrow>WHAT YOU CAN DO</Eyebrow>
          <Text style={s.bullet}>· Wait until next month for free analyses to reset</Text>
          <Text style={s.bullet}>· Use any remaining bonus credits on your account</Text>
          <Text style={s.bullet}>· Contact support if you need Pro access for testing</Text>
        </Card>
      ) : null}

      <Text style={s.note}>
        Pro subscriptions and Re-Up packs are managed server-side (RevenueCat webhooks). This
        Lite build does not open the App Store purchase sheet.
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
