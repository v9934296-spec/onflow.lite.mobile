import React, { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Linking,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppNav } from "../src/components/AppNav";
import { track } from "../src/analytics";
import { deleteMyAccount, exportMyData } from "../src/api/accountApi";
import {
  fetchProgressionOverview,
  type ProgressionOverview,
} from "../src/api/progressionApi";
import { useAccount } from "../src/auth/accountContext";
import { useAuth } from "../src/auth/authContext";
import { isProTier, PAYWALL_ROUTE, usePurchases } from "../src/billing";
import { DELETE_ACCOUNT_INFO_URL, PRIVACY_URL, TERMS_URL } from "../src/legal/urls";
import { C, F, RADIUS, SPACE } from "../src/theme";
import { Btn, Card, Eyebrow, SkeletonLines } from "../src/ui";

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
  const { isProEntitled, showCustomerCenter } = usePurchases();
  const [overview, setOverview] = useState<ProgressionOverview | null>(null);
  const [loadingStats, setLoadingStats] = useState(true);
  const [busy, setBusy] = useState<"export" | "delete" | "manage" | null>(null);
  const [signingOut, setSigningOut] = useState(false);
  const isPro = isProEntitled || isProTier(user?.tier);

  const handleSignOut = useCallback(async () => {
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
  }, [busy, signOut, signingOut]);

  useEffect(() => {
    let cancelled = false;
    void fetchProgressionOverview().then((result) => {
      if (cancelled) return;
      if (result.ok) setOverview(result.data);
      setLoadingStats(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

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

  const displayName = user?.email?.split("@")[0] ?? user?.user_id ?? "Skater";

  return (
    <View style={[s.screen, { paddingTop: insets.top + 12, paddingBottom: insets.bottom }]}>
      <ScrollView contentContainerStyle={s.content}>
        <View style={{ gap: 6 }}>
          <Eyebrow color={C.red}>ONFLOW</Eyebrow>
          <Text style={s.title}>Profile</Text>
        </View>

        <Card accent={C.volt}>
          <View style={s.avatarRow}>
            <View style={s.avatar}>
              <Text style={s.avatarLetter}>{displayName.slice(0, 1).toUpperCase()}</Text>
            </View>
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={s.value}>{user?.email || user?.user_id || "Signed out"}</Text>
              <Text style={s.meta}>{String(user?.tier ?? "guest").toUpperCase()} PLAN</Text>
            </View>
          </View>
        </Card>

        {loadingStats ? (
          <Card>
            <SkeletonLines widths={["40%", "70%"]} />
          </Card>
        ) : overview ? (
          <Card>
            <Eyebrow>YOUR STATS</Eyebrow>
            <View style={s.stats}>
              <Stat label="Sessions" value={String(overview.total_sessions)} />
              <Stat label="Make rate" value={`${Math.round(overview.global_make_rate)}%`} />
              <Stat label="Streak" value={String(overview.current_streak)} />
            </View>
          </Card>
        ) : null}

        {!isPro ? (
          <Btn label="Upgrade to Pro" onPress={() => router.push(PAYWALL_ROUTE)} />
        ) : (
          <Btn
            label={busy === "manage" ? "Opening…" : "Manage subscription"}
            variant="ghost"
            onPress={() => {
              if (busy) return;
              setBusy("manage");
              void showCustomerCenter()
                .then((result) => {
                  if (!result.ok) {
                    Alert.alert(
                      "Customer Center",
                      result.message ?? "Could not open subscription management.",
                    );
                  }
                })
                .finally(() => setBusy(null));
            }}
          />
        )}

        <View style={s.group}>
          <Row label="Feed" onPress={() => router.push("/feed" as never)} />
          <Row label="Session history" onPress={() => router.push("/history" as never)} />
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

        <View style={{ gap: 10, marginTop: SPACE.md }}>
          <Btn
            label={signingOut ? "Signing out…" : "Sign out"}
            variant="red"
            onPress={() => void handleSignOut()}
            disabled={signingOut || Boolean(busy)}
          />
          <Btn label="Back to Home" variant="ghost" onPress={() => router.replace("/" as never)} />
        </View>
      </ScrollView>
      <AppNav />
    </View>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={s.stat}>
      <Text style={s.statValue}>{value}</Text>
      <Text style={s.statLabel}>{label}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  content: { paddingHorizontal: SPACE.lg, paddingBottom: SPACE.xl, gap: SPACE.lg },
  title: { fontFamily: F.heading, fontSize: 32, color: C.offwhite },
  avatarRow: { flexDirection: "row", alignItems: "center", gap: SPACE.md },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: C.charcoal3,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarLetter: { fontFamily: F.heading, fontSize: 22, color: C.volt },
  value: { fontFamily: F.bold, fontSize: 15, color: C.offwhite },
  meta: { fontFamily: F.mono, fontSize: 9, letterSpacing: 0.8, color: C.dim },
  stats: { flexDirection: "row", gap: SPACE.lg },
  stat: { gap: 2 },
  statValue: { fontFamily: F.monoBold, fontSize: 20, color: C.offwhite },
  statLabel: { fontFamily: F.mono, fontSize: 10, color: C.dim, textTransform: "uppercase" },
  group: { backgroundColor: C.charcoal2, borderRadius: RADIUS.lg, overflow: "hidden" },
  row: {
    minHeight: 58,
    paddingHorizontal: SPACE.lg,
    flexDirection: "row",
    alignItems: "center",
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.charcoal3,
  },
  rowLabel: { fontFamily: F.bold, fontSize: 14, color: C.offwhite },
  rowValue: { fontFamily: F.body, fontSize: 11, color: C.dim, marginTop: 2 },
  chevron: { fontFamily: F.body, fontSize: 24, color: C.dim },
});
