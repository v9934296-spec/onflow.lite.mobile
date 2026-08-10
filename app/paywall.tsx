import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { useAccount } from "../src/auth/accountContext";
import {
  isProTier,
  isPurchaseCancelledError,
  purchasesErrorMessage,
  usePurchases,
  RC_ENTITLEMENT_PRO,
} from "../src/billing";
import { PRIVACY_URL, TERMS_URL } from "../src/legal/urls";
import { C, F, RADIUS, SPACE, withOpacity } from "../src/theme";
import { Btn, Eyebrow } from "../src/ui";

type PaywallMode = "upgrade" | "pro" | "reup";
type BusyKind = "yearly" | "monthly" | "reup" | "restore" | "manage" | null;

const FREE_PERKS = [
  "3 AI analyses / month",
  "Clips up to 10 seconds",
  "Core session tracking",
  "Trick logging",
  "Session history",
] as const;

const PRO_PERKS = [
  "30 AI analyses / month",
  "Clips up to 20 seconds",
  "Full AI trick feedback",
  "Progression insights",
  "Complete session history",
] as const;

const PRO_ACTIVE_PERKS = [
  "30 AI analyses / month",
  "Clips up to 20 seconds",
  "Full AI trick feedback",
  "Progression insights",
] as const;

function PerkRow({ text, muted = false }: { text: string; muted?: boolean }) {
  return (
    <View style={s.perkRow}>
      <Text style={[s.perkMark, muted && { color: C.dim }]}>•</Text>
      <Text style={[s.perkText, muted && { color: C.dim }]}>{text}</Text>
    </View>
  );
}

/**
 * OnFlow Pro paywall — three states:
 * upgrade (Free vs Pro), active Pro management, and Re-Up when analyses are spent.
 */
export default function PaywallScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ mode?: string }>();
  const { user, refreshUser } = useAccount();
  const {
    ready,
    isProEntitled,
    packages,
    showCustomerCenter,
    restore,
    refresh,
    purchasePackage,
    purchaseReUp,
  } = usePurchases();
  const [busy, setBusy] = useState<BusyKind>(null);

  const isPro = isProEntitled || isProTier(user?.tier);
  const wantsReup = params.mode === "reup";

  const mode: PaywallMode = useMemo(() => {
    if (wantsReup && isPro) return "reup";
    if (isPro) return "pro";
    return "upgrade";
  }, [wantsReup, isPro]);

  const yearlyPrice = packages.yearly?.product.priceString ?? "$89.99";
  const monthlyPrice = packages.monthly?.product.priceString ?? "$9.99";

  useEffect(() => {
    track("paywall_viewed", { tier: user?.tier ?? "unknown", mode });
  }, [user?.tier, mode]);

  const onPurchase = useCallback(
    async (kind: "yearly" | "monthly") => {
      if (busy) return;
      setBusy(kind);
      try {
        await purchasePackage(kind);
        await refreshUser();
        Alert.alert("Welcome to Pro", "Your Pro access is active. Skate more — get more feedback.");
      } catch (error) {
        if (isPurchaseCancelledError(error)) return;
        Alert.alert("Purchase failed", purchasesErrorMessage(error));
      } finally {
        setBusy(null);
      }
    },
    [busy, purchasePackage, refreshUser],
  );

  const onReUp = useCallback(async () => {
    if (busy) return;
    setBusy("reup");
    try {
      await purchaseReUp();
      await refreshUser();
      Alert.alert("Re-Up complete", "+10 AI analyses added. They stay available until you use them.");
    } catch (error) {
      if (isPurchaseCancelledError(error)) return;
      Alert.alert("Purchase failed", purchasesErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }, [busy, purchaseReUp, refreshUser]);

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
      const entitled = typeof info.entitlements.active[RC_ENTITLEMENT_PRO] !== "undefined";
      Alert.alert(
        entitled ? "Purchases restored" : "No Pro found",
        entitled
          ? "Your OnFlow Pro access has been restored."
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
        Alert.alert("Manage subscription", result.message ?? "Could not open subscription management.");
      }
    } finally {
      setBusy(null);
    }
  }, [busy, refresh, refreshUser, showCustomerCenter]);

  return (
    <View style={[s.screen, { paddingTop: insets.top + 12, paddingBottom: insets.bottom + 12 }]}>
      <ScrollView
        contentContainerStyle={s.scroll}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <Pressable onPress={() => router.back()} hitSlop={12} style={s.closeRow}>
          <Text style={s.close}>Close</Text>
        </Pressable>

        <Eyebrow color={C.volt}>ONFLOW PRO</Eyebrow>

        {!ready ? (
          <View style={s.loadingRow}>
            <ActivityIndicator color={C.volt} />
            <Text style={s.meta}>Connecting to store…</Text>
          </View>
        ) : null}

        {mode === "upgrade" ? (
          <>
            <Text style={s.title}>
              {wantsReup ? "You're out of analyses" : "Skate more. Get more feedback."}
            </Text>
            <Text style={s.sub}>
              {wantsReup
                ? "Upgrade to Pro for more AI trick analysis, longer clips, and deeper feedback."
                : "Turn your sessions into real progression with more AI trick analysis, longer clips, and deeper feedback."}
            </Text>

            <View style={s.compare}>
              <View style={s.tierCol}>
                <Text style={s.tierLabel}>FREE</Text>
                {FREE_PERKS.map((p) => (
                  <PerkRow key={p} text={p} muted />
                ))}
              </View>
              <View style={[s.tierCol, s.tierColPro]}>
                <Text style={[s.tierLabel, { color: C.volt }]}>PRO</Text>
                {PRO_PERKS.map((p) => (
                  <PerkRow key={p} text={p} />
                ))}
              </View>
            </View>

            <View style={s.annualCard}>
              <View style={s.bestBadge}>
                <Text style={s.bestBadgeText}>BEST VALUE</Text>
              </View>
              <Text style={s.planName}>ANNUAL</Text>
              <Text style={s.price}>
                {yearlyPrice}
                <Text style={s.priceUnit}> / year</Text>
              </Text>
              <Text style={s.meta}>About $7.50 / month · Save 25%</Text>
              <Btn
                label={busy === "yearly" ? "Starting…" : `Start Pro — ${yearlyPrice}/year`}
                onPress={() => void onPurchase("yearly")}
                loading={busy === "yearly"}
                disabled={!!busy && busy !== "yearly"}
              />
            </View>

            <Text style={s.or}>or</Text>

            <View style={s.monthlyBlock}>
              <Text style={s.planName}>MONTHLY</Text>
              <Text style={s.price}>
                {monthlyPrice}
                <Text style={s.priceUnit}> / month</Text>
              </Text>
              <Btn
                label={busy === "monthly" ? "Starting…" : `Start Pro — ${monthlyPrice}/month`}
                variant="surface"
                onPress={() => void onPurchase("monthly")}
                loading={busy === "monthly"}
                disabled={!!busy && busy !== "monthly"}
              />
            </View>

            <Text style={s.restoreHint}>Already subscribed?</Text>
            <Btn
              label={busy === "restore" ? "Restoring…" : "Restore purchases"}
              variant="ghost"
              onPress={() => void onRestore()}
              loading={busy === "restore"}
              disabled={!!busy && busy !== "restore"}
            />
          </>
        ) : null}

        {mode === "pro" ? (
          <>
            <Text style={s.title}>You're on Pro</Text>
            <Text style={s.sub}>Your Pro access is active.</Text>
            <View style={s.proActiveList}>
              {PRO_ACTIVE_PERKS.map((p) => (
                <PerkRow key={p} text={p} />
              ))}
            </View>
            {user?.bonus_analyses_remaining != null && user.bonus_analyses_remaining > 0 ? (
              <Text style={s.meta}>Re-Up analyses remaining: {user.bonus_analyses_remaining}</Text>
            ) : null}
            <Btn
              label={busy === "manage" ? "Opening…" : "Manage subscription"}
              onPress={() => void onManage()}
              loading={busy === "manage"}
              disabled={!!busy && busy !== "manage"}
            />
          </>
        ) : null}

        {mode === "reup" ? (
          <>
            <Text style={s.title}>You're out of analyses</Text>
            <Text style={s.sub}>Your monthly Pro analyses have been used.</Text>
            <Text style={[s.sub, { marginTop: 4 }]}>Need a few more before your allowance resets?</Text>

            <View style={s.reupCard}>
              <Eyebrow color={C.volt}>RE-UP</Eyebrow>
              <Text style={s.reupHeadline}>+10 AI analyses</Text>
              <Text style={s.price}>
                $4.99
                <Text style={s.priceUnit}> one-time purchase</Text>
              </Text>
              <Text style={s.meta}>Your Re-Up analyses stay available until you use them.</Text>
              <Btn
                label={busy === "reup" ? "Purchasing…" : "Re-Up +10 — $4.99"}
                onPress={() => void onReUp()}
                loading={busy === "reup"}
                disabled={!!busy && busy !== "reup"}
              />
            </View>
            <Text style={s.fine}>Your Pro subscription is unchanged.</Text>
            <Btn
              label={busy === "manage" ? "Opening…" : "Manage subscription"}
              variant="ghost"
              onPress={() => void onManage()}
              loading={busy === "manage"}
              disabled={!!busy && busy !== "manage"}
            />
          </>
        ) : null}

        <View style={s.legalRow}>
          <Pressable onPress={() => void Linking.openURL(TERMS_URL)}>
            <Text style={s.legalLink}>Terms of Use</Text>
          </Pressable>
          <Text style={s.legalDot}>·</Text>
          <Pressable onPress={() => void Linking.openURL(PRIVACY_URL)}>
            <Text style={s.legalLink}>Privacy Policy</Text>
          </Pressable>
        </View>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  scroll: { paddingHorizontal: 24, gap: 14, paddingBottom: 28 },
  closeRow: { alignSelf: "flex-end", marginBottom: 4 },
  close: { fontFamily: F.medium, fontSize: 14, color: C.dim },
  title: {
    fontFamily: F.heading,
    fontSize: 28,
    lineHeight: 34,
    color: C.offwhite,
    textTransform: "uppercase",
    textShadowColor: withOpacity(C.volt, 0.35),
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 12,
  },
  sub: { fontFamily: F.body, fontSize: 14, lineHeight: 20, color: C.muted },
  compare: { flexDirection: "row", gap: 12, marginTop: 4 },
  tierCol: {
    flex: 1,
    gap: 6,
    padding: SPACE.md,
    backgroundColor: C.charcoal2,
    borderRadius: RADIUS.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.charcoal5,
  },
  tierColPro: {
    borderColor: withOpacity(C.volt, 0.55),
    shadowColor: C.volt,
    shadowOpacity: 0.25,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 0 },
    elevation: 3,
  },
  tierLabel: {
    fontFamily: F.bold,
    fontSize: 13,
    letterSpacing: 1.2,
    color: C.dim,
    marginBottom: 4,
  },
  perkRow: { flexDirection: "row", gap: 6, alignItems: "flex-start" },
  perkMark: { fontFamily: F.bold, fontSize: 13, color: C.volt, lineHeight: 18 },
  perkText: { flex: 1, fontFamily: F.body, fontSize: 12, lineHeight: 18, color: C.offwhite },
  annualCard: {
    marginTop: 8,
    gap: 8,
    padding: SPACE.lg,
    borderRadius: RADIUS.lg,
    backgroundColor: C.charcoal2,
    borderWidth: 1,
    borderColor: withOpacity(C.volt, 0.65),
    shadowColor: C.volt,
    shadowOpacity: 0.3,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 0 },
    elevation: 4,
  },
  bestBadge: {
    alignSelf: "flex-start",
    backgroundColor: C.volt,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: RADIUS.sm,
  },
  bestBadgeText: {
    fontFamily: F.bold,
    fontSize: 11,
    letterSpacing: 1,
    color: C.charcoal,
  },
  planName: {
    fontFamily: F.bold,
    fontSize: 13,
    letterSpacing: 1.4,
    color: C.dim,
  },
  price: {
    fontFamily: F.heading,
    fontSize: 32,
    color: C.offwhite,
  },
  priceUnit: {
    fontFamily: F.body,
    fontSize: 15,
    color: C.dim,
  },
  meta: { fontFamily: F.body, fontSize: 13, lineHeight: 18, color: C.dim },
  or: {
    fontFamily: F.medium,
    fontSize: 13,
    color: C.dim,
    textAlign: "center",
  },
  monthlyBlock: { gap: 8 },
  restoreHint: {
    fontFamily: F.medium,
    fontSize: 13,
    color: C.muted,
    textAlign: "center",
    marginTop: 8,
  },
  proActiveList: { gap: 8, marginVertical: 8 },
  reupCard: {
    gap: 8,
    padding: SPACE.lg,
    borderRadius: RADIUS.lg,
    backgroundColor: C.charcoal2,
    borderWidth: 1,
    borderColor: withOpacity(C.volt, 0.65),
    shadowColor: C.volt,
    shadowOpacity: 0.28,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 0 },
    elevation: 4,
  },
  reupHeadline: {
    fontFamily: F.heading,
    fontSize: 26,
    color: C.volt,
    textTransform: "uppercase",
  },
  fine: {
    fontFamily: F.body,
    fontSize: 12,
    color: C.dim,
    textAlign: "center",
  },
  legalRow: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: 8,
    marginTop: 12,
  },
  legalLink: {
    fontFamily: F.medium,
    fontSize: 12,
    color: C.dim,
    textDecorationLine: "underline",
  },
  legalDot: { fontFamily: F.body, fontSize: 12, color: C.dim },
  loadingRow: { flexDirection: "row", alignItems: "center", gap: 8 },
});
