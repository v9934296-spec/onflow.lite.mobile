import React, { useEffect } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { AppNav } from "../src/components/AppNav";
import { FeedCard } from "../src/components/FeedCard";
import { track } from "../src/analytics";
import { useFeed } from "../src/feed/useFeed";
import { C, F, SPACE, withOpacity } from "../src/theme";
import { Btn, Card, Eyebrow } from "../src/ui";

export default function FeedScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const {
    items,
    cursor,
    lifecycleStage,
    loading,
    refreshing,
    loadingMore,
    error,
    refresh,
    loadMore,
    retry,
  } = useFeed();

  useEffect(() => {
    track("feed_viewed");
  }, []);

  const showEmpty = !loading && !error && items.length === 0 && lifecycleStage === "stage_a";

  return (
    <View style={[s.screen, { paddingTop: insets.top + 12, paddingBottom: insets.bottom }]}>
      <View style={s.content}>
        <View style={{ gap: 6 }}>
          <Eyebrow color={C.red}>SKATE CIRCLE</Eyebrow>
          <Text style={s.title}>Feed</Text>
          <Text style={s.sub}>
            Progress worth seeing — sessions, clips, battles and breakthroughs.
          </Text>
          <Btn label="Back to Home" variant="ghost" onPress={() => router.replace("/" as never)} />
        </View>

        {loading ? (
          <View style={s.centered}>
            <ActivityIndicator color={C.volt} />
            <Text style={s.hint}>Loading feed…</Text>
          </View>
        ) : error ? (
          <View style={[s.centered, s.errorCard]}>
            <Text style={s.error}>{error}</Text>
            <Btn label="Retry" variant="red" onPress={() => void retry()} />
          </View>
        ) : showEmpty ? (
          <View style={s.centered}>
            <Card accent={C.volt} style={s.emptyCard}>
              <Eyebrow color={C.volt}>YOUR CIRCLE</Eyebrow>
              <Text style={s.emptyTitle}>Nothing fake to fill the feed.</Text>
              <Text style={s.hint}>
                Session recaps and real progression events will appear here as your circle skates.
              </Text>
            </Card>
          </View>
        ) : (
          <FlatList
            data={items}
            keyExtractor={(item) => item.id}
            contentContainerStyle={{ gap: SPACE.md, paddingBottom: 18 }}
            refreshControl={
              <RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={C.volt} />
            }
            renderItem={({ item }) => (
              <FeedCard
                event={item}
                showReactions={lifecycleStage !== "stage_a"}
              />
            )}
            onEndReached={() => {
              if (cursor) void loadMore();
            }}
            onEndReachedThreshold={0.4}
            ListFooterComponent={
              loadingMore ? <ActivityIndicator color={C.volt} style={{ marginTop: 12 }} /> : null
            }
            ListEmptyComponent={
              <Text style={s.hint}>No feed events yet. Check back after your next session.</Text>
            }
          />
        )}
      </View>
      <AppNav />
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  content: { flex: 1, paddingHorizontal: SPACE.lg, paddingTop: SPACE.md, gap: SPACE.md },
  title: {
    fontFamily: F.heading,
    fontSize: 34,
    color: C.offwhite,
    textShadowColor: withOpacity(C.volt, 0.35),
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 12,
  },
  sub: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
  centered: { flex: 1, justifyContent: "center", alignItems: "center", gap: 12 },
  hint: { fontFamily: F.body, fontSize: 13, color: C.dim, textAlign: "center", lineHeight: 19 },
  emptyCard: {
    backgroundColor: C.charcoal,
    shadowColor: C.volt,
    shadowOpacity: 0.28,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 0 },
    elevation: 4,
  },
  emptyTitle: { fontFamily: F.bold, fontSize: 17, color: C.offwhite, marginTop: 4 },
  errorCard: {
    backgroundColor: C.charcoal,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: withOpacity(C.red, 0.45),
    borderRadius: 12,
    padding: SPACE.lg,
    shadowColor: C.red,
    shadowOpacity: 0.3,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 0 },
  },
  error: { fontFamily: F.body, fontSize: 13, color: C.red, textAlign: "center" },
});
