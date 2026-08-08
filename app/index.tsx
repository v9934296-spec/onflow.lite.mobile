import React, { useCallback, useEffect, useState } from "react";
import {
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppNav } from "../src/components/AppNav";
import { CurrentFocusHeader } from "../src/components/CurrentFocusHeader";
import { TrickCard } from "../src/components/TrickCard";
import { useAccount } from "../src/auth/accountContext";
import { useSkateSession } from "../src/skateSession/skateSessionContext";
import {
  fetchProgressionOverview,
  fetchTrickStats,
  fetchWhatsNext,
  type ProgressionOverview,
  type TrickStatSummary,
  type WhatsNextPayload,
} from "../src/api/progressionApi";
import {
  adaptTrickStats,
  buildCurrentFocus,
  formatTrickDisplay,
  pickActiveBattle,
} from "../src/progressionAdapter";
import { C, F, SPACE, withOpacity } from "../src/theme";
import { Card, Eyebrow, SkeletonLines } from "../src/ui";

type LoadState = "loading" | "ready" | "error";

export default function Home() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { user } = useAccount();
  const { hasActiveSession, activeSession } = useSkateSession();

  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<ProgressionOverview | null>(null);
  const [whatsNext, setWhatsNext] = useState<WhatsNextPayload | null>(null);
  const [rawTricks, setRawTricks] = useState<TrickStatSummary[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setState("loading");
    setError(null);

    const [overviewResult, whatsNextResult, tricksResult] = await Promise.all([
      fetchProgressionOverview(),
      fetchWhatsNext(),
      fetchTrickStats(),
    ]);

    if (!overviewResult.ok && !tricksResult.ok) {
      setError(overviewResult.ok === false ? overviewResult.error.message : "Could not load home.");
      setState("error");
      setRefreshing(false);
      return;
    }

    setOverview(overviewResult.ok ? overviewResult.data : null);
    setWhatsNext(whatsNextResult.ok ? whatsNextResult.data : null);
    setRawTricks(tricksResult.ok ? tricksResult.data : []);
    setState("ready");
    setRefreshing(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const tricks = adaptTrickStats(rawTricks);
  const focus = buildCurrentFocus(whatsNext, rawTricks);
  const battle = pickActiveBattle(tricks);
  const isBattleLive = activeSession?.notes?.startsWith("[battle]") ?? false;

  return (
    <View style={[s.screen, { paddingTop: insets.top + 12, paddingBottom: insets.bottom }]}>
      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => void load(true)}
            tintColor={C.volt}
          />
        }
      >
        <View style={s.topline}>
          <Eyebrow color={C.volt}>ONFLOW</Eyebrow>
          <Pressable onPress={() => router.push("/settings" as never)} hitSlop={12}>
            <Text style={s.link}>PROFILE</Text>
          </Pressable>
        </View>

        {user?.email ? <Text style={s.account}>{user.email}</Text> : null}

        {state === "loading" ? (
          <Card>
            <SkeletonLines testID="home-loading" />
          </Card>
        ) : null}

        {state === "error" ? (
          <Card accent={C.red}>
            <Text style={s.error}>{error ?? "Something went wrong."}</Text>
            <Pressable onPress={() => void load()}>
              <Text style={s.retry}>Tap to retry</Text>
            </Pressable>
          </Card>
        ) : null}

        {state === "ready" ? (
          <>
            {hasActiveSession ? (
              <Card
                accent={isBattleLive ? C.red : C.volt}
                onPress={() => router.replace("/flow" as never)}
              >
                <Eyebrow color={isBattleLive ? C.red : C.volt}>
                  {isBattleLive ? "BATTLE LIVE" : "SESSION LIVE"}
                </Eyebrow>
                <Text style={s.cardTitle}>Continue skating</Text>
                <Text style={s.cardSub}>Pick up where you left off.</Text>
              </Card>
            ) : null}

            {battle ? (
              <Card accent={C.red} onPress={() => router.replace("/flow" as never)}>
                <Eyebrow color={C.red}>BATTLE</Eyebrow>
                <Text style={s.cardTitle}>{battle.display_name}</Text>
                <Text style={s.cardSub}>
                  {battle.make_rate_pct}% make rate · keep pressure on until it flips.
                </Text>
              </Card>
            ) : null}

            <CurrentFocusHeader
              focus={focus}
              onPress={() => router.replace("/flow" as never)}
            />

            {whatsNext?.has_recommendation ? (
              <Card accent={C.volt}>
                <Eyebrow color={C.volt}>OBJECTIVE</Eyebrow>
                <Text style={s.cardTitle}>
                  {whatsNext.focus_trick
                    ? formatTrickDisplay(whatsNext.focus_trick)
                    : "What's next"}
                </Text>
                <Text style={s.cardSub}>{whatsNext.message}</Text>
                {whatsNext.focus_cue ? (
                  <Text style={s.cue}>Cue: {whatsNext.focus_cue}</Text>
                ) : null}
              </Card>
            ) : null}

            {overview ? (
              <Card accent={C.volt}>
                <Eyebrow color={C.volt}>PROGRESS SUMMARY</Eyebrow>
                <View style={s.rateScale}>
                  <View style={s.rateTrack}>
                    <View
                      style={[
                        s.rateFill,
                        {
                          width: `${Math.max(0, Math.min(100, Math.round(overview.global_make_rate)))}%`,
                        },
                      ]}
                    />
                  </View>
                  <Text style={s.rateScaleValue}>{Math.round(overview.global_make_rate)}%</Text>
                </View>
                <View style={s.metrics}>
                  <Metric label="Make rate" value={`${Math.round(overview.global_make_rate)}%`} />
                  <Metric label="Sessions" value={String(overview.total_sessions)} />
                  <Metric label="Streak" value={String(overview.current_streak)} />
                  <Metric label="This week" value={String(overview.sessions_this_week)} />
                </View>
              </Card>
            ) : null}

            {tricks.length > 0 ? (
              <View style={s.section}>
                <Text style={s.sectionTitle}>YOUR FLOW</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.trickRow}>
                  {tricks.slice(0, 8).map((trick) => (
                    <TrickCard
                      key={trick.trick_id}
                      trick={trick}
                      onPress={() => router.replace("/pte" as never)}
                    />
                  ))}
                </ScrollView>
              </View>
            ) : null}

            <View style={s.quickLinks}>
              <QuickLink label="Feed" onPress={() => router.push("/feed" as never)} />
              <QuickLink label="History" onPress={() => router.push("/history" as never)} />
              <QuickLink label="Notifications" onPress={() => router.push("/notifications" as never)} />
              <QuickLink label="Start session" onPress={() => router.replace("/flow" as never)} accent={C.volt} />
            </View>
          </>
        ) : null}
      </ScrollView>
      <AppNav />
    </View>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={s.metric}>
      <Text style={s.metricValue}>{value}</Text>
      <Text style={s.metricLabel}>{label}</Text>
    </View>
  );
}

function QuickLink({
  label,
  onPress,
  accent,
}: {
  label: string;
  onPress: () => void;
  accent?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        s.quick,
        pressed && { opacity: 0.75 },
        accent
          ? {
              borderColor: accent,
              backgroundColor: withOpacity(accent, 0.1),
            }
          : null,
      ]}
    >
      <Text style={[s.quickText, accent ? { color: accent } : null]}>{label.toUpperCase()}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  scroll: { flex: 1 },
  content: { paddingHorizontal: SPACE.lg, paddingBottom: SPACE.xl, gap: SPACE.lg },
  topline: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  link: { fontFamily: F.bold, fontSize: 11, letterSpacing: 0.8, color: C.volt },
  account: { fontFamily: F.mono, fontSize: 11, color: C.dim, marginTop: -8 },
  error: { fontFamily: F.body, color: C.offwhite, fontSize: 14 },
  retry: { fontFamily: F.bold, color: C.volt, marginTop: 8 },
  cardTitle: { fontFamily: F.heading, fontSize: 22, color: C.offwhite, lineHeight: 28 },
  cardSub: { fontFamily: F.body, fontSize: 14, lineHeight: 20, color: C.dim },
  cue: { fontFamily: F.mono, fontSize: 12, color: C.volt, marginTop: 4 },
  rateScale: { flexDirection: "row", alignItems: "center", gap: SPACE.md, marginBottom: 4 },
  rateTrack: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    backgroundColor: C.charcoal4,
    overflow: "hidden",
  },
  rateFill: {
    height: "100%",
    borderRadius: 2,
    backgroundColor: C.volt,
  },
  rateScaleValue: { fontFamily: F.monoBold, fontSize: 18, color: C.volt, minWidth: 48, textAlign: "right" },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: SPACE.md },
  metric: { width: "45%", gap: 2 },
  metricValue: { fontFamily: F.monoBold, fontSize: 26, color: C.volt },
  metricLabel: { fontFamily: F.mono, fontSize: 11, color: C.dim, textTransform: "uppercase" },
  section: { gap: SPACE.md },
  sectionTitle: {
    fontFamily: F.medium,
    fontSize: 12,
    letterSpacing: 0.8,
    color: C.dim,
    textTransform: "uppercase",
  },
  trickRow: { gap: SPACE.md, paddingRight: SPACE.lg },
  quickLinks: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: SPACE.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: C.charcoal4,
    paddingTop: SPACE.md,
  },
  quick: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: C.charcoal5,
    backgroundColor: "transparent",
    borderRadius: 4,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  quickText: { fontFamily: F.bold, fontSize: 11, color: C.muted, letterSpacing: 0.6 },
});
