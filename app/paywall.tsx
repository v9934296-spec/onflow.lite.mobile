import React, { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Alert, Linking, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { useAccount } from "../src/auth/accountContext";
import {
  isProTier,
  isNativeStorePlatform,
  purchasesErrorMessage,
  usePurchases,
  RC_ENTITLEMENT_PRO,
  RC_PACKAGE_IDS,
} from "../src/billing";
import { PRIVACY_URL, TERMS_URL } from "../src/legal/urls";
import { C, F, withOpacity } from "../src/theme";
import { Btn, Card, Eyebrow } from "../src/ui";

/**
 * Pro upgrade surface: presents the RevenueCat Paywall (dashboard-configured)
 * for lifetime / yearly / monthly packages attached to entitlement `onflow-lite Pro`.
 */
export default function PaywallScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user, refreshUser } = useAccount();
  const {
    ready,
    isProEntitled,
    packages,
    showPaywall,
    showCustomerCenter,
    restore,
    refresh,
  } = usePurchases();
  const [busy, setBusy] = useState<"paywall" | "restore" | "manage" | null>(null);
  const autoPresented = useRef(false);

  const isPro = isProEntitled || isProTier(user?.tier);

  useEffect(() => {
    track("paywall_viewed", { tier: user?.tier ?? "unknown" });
  }, [user?.tier]);

  const runPaywall = useCallback(async () => {
    if (busy) return;
    setBusy("paywall");
    try {
      const result = await showPaywall();
      await refreshUser();
      if (result.status === "purchased" || result.status === "restored") {
        Alert.alert(
          "Welcome to Pro",
          "Purchase recorded. Your store entitlement is active. "
            + "If analysis still shows a free-tier limit for a moment, wait for billing sync — usually under a minute.",
        );
        return;
      }
      if (result.status === "error" || result.status === "unsupported") {
        Alert.alert("Paywall unavailable", result.message ?? "Could not open the paywall.");
      }
    } catch (error) {
      Alert.alert("Paywall error", purchasesErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }, [busy, refreshUser, showPaywall]);

  // Auto-present RC paywall once when the user lacks Pro (native only).
  useEffect(() => {
    if (!ready || isPro || autoPresented.current || !isNativeStorePlatform()) return;
    autoPresented.current = true;
    void runPaywall();
  }, [ready, isPro, runPaywall]);

  const onRestore = useCallback(async () => {
    if (busy) return;
    setBusy("restore");
    try {
      const info = await restore();
      await refreshUser();
      if (!info) {
        Alert.alert("Restore failed", "Could not restore purchases. Try again or contact support.");
        return;
      }
      const entitled =
        typeof info.entitlements.active[RC_ENTITLEMENT_PRO] !== "undefined";
      Alert.alert(
        entitled ? "Purchases restored" : "No Pro found",
        entitled
          ? "Your onflow-lite Pro access has been restored."
          : "We could not find an active Pro purchase for this Apple/Google account.",
      );
    } catch (error) {
      Alert.alert("Restore failed", purchasesErrorMessage(error, "Restore failed."));
    } finally {
      setBusy(null);
    }
  }, [busy, refreshUser, restore]);

  const onManage = useCallback(async () => {
    if (busy) return;
    setBusy("manage");
    try {
      const result = await showCustomerCenter();
      await refresh();
      await refreshUser();
      if (!result.ok) {
        Alert.alert("Customer Center", result.message ?? "Could not open subscription management.");
      }
    } finally {
      setBusy(null);
    }
  }, [busy, refresh, refreshUser, showCustomerCenter]);

  const packageSummary = [
    packages.lifetime ? `Lifetime (${RC_PACKAGE_IDS.lifetime})` : null,
    packages.yearly ? `Yearly (${RC_PACKAGE_IDS.yearly})` : null,
    packages.monthly ? `Monthly (${RC_PACKAGE_IDS.monthly})` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <View style={{ gap: 6 }}>
        <Eyebrow color={C.volt}>ONFLOW LITE PRO</Eyebrow>
        <Text style={s.title}>{isPro ? "You're on Pro" : "Unlock unlimited analysis"}</Text>
        <Text style={s.sub}>
          {isPro
            ? "Your onflow-lite Pro entitlement is active. Manage billing anytime in Customer Center."
            : "Choose Lifetime, Yearly, or Monthly. Purchases sync through RevenueCat to your OnFlow account."}
        </Text>
      </View>

      <Card accent={C.volt} style={s.planCard}>
        <Eyebrow color={C.volt}>CURRENT PLAN</Eyebrow>
        <Text style={s.plan}>{isPro ? "Pro" : user?.tier ?? "free"}</Text>
        {user?.bonus_analyses_remaining != null && user.bonus_analyses_remaining > 0 ? (
          <Text style={s.meta}>Bonus analyses remaining: {user.bonus_analyses_remaining}</Text>
        ) : null}
        {!ready ? (
          <View style={s.loadingRow}>
            <ActivityIndicator color={C.volt} />
            <Text style={s.meta}>Connecting to store…</Text>
          </View>
        ) : packageSummary ? (
          <Text style={s.meta}>Offering packages: {packageSummary}</Text>
        ) : (
          <Text style={s.meta}>
            Configure packages `{RC_PACKAGE_IDS.lifetime}`, `{RC_PACKAGE_IDS.yearly}`, `
            {RC_PACKAGE_IDS.monthly}` on your current Offering in RevenueCat.
          </Text>
        )}
      </Card>

      <View style={{ gap: 10 }}>
        {!isPro ? (
          <>
            <Btn
              label={busy === "paywall" ? "Opening…" : "View Pro plans"}
              onPress={() => void runPaywall()}
            />
            <Btn
              label={busy === "restore" ? "Restoring…" : "Restore purchases"}
              variant="ghost"
              onPress={() => void onRestore()}
            />
          </>
        ) : (
          <Btn
            label={busy === "manage" ? "Opening…" : "Manage subscription"}
            onPress={() => void onManage()}
          />
        )}
        <Btn label="Terms of Service" variant="ghost" onPress={() => void Linking.openURL(TERMS_URL)} />
        <Btn label="Privacy Policy" variant="ghost" onPress={() => void Linking.openURL(PRIVACY_URL)} />
        <Btn label="Back" variant="ghost" onPress={() => router.back()} />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24, gap: 14 },
  title: {
    fontFamily: F.heading,
    fontSize: 28,
    color: C.offwhite,
    textShadowColor: withOpacity(C.volt, 0.35),
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 12,
  },
  sub: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
  planCard: {
    backgroundColor: C.charcoal,
    shadowColor: C.volt,
    shadowOpacity: 0.3,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 0 },
    elevation: 4,
  },
  plan: {
    fontFamily: F.heading,
    fontSize: 28,
    color: C.volt,
    marginTop: 4,
    textTransform: "capitalize",
    textShadowColor: withOpacity(C.volt, 0.4),
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 10,
  },
  meta: { fontFamily: F.body, fontSize: 13, color: C.dim, marginTop: 4 },
  loadingRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 8 },
});
