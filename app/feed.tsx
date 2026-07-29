import React, { useEffect } from "react";
import { ActivityIndicator, FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { formatEventHeadline, formatEventTime } from "../src/feed/formatHeadline";
import { useFeed } from "../src/feed/useFeed";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow } from "../src/ui";
import type { FeedEvent } from "../src/types/feedEvent";

function FeedEventCard({ event }: { event: FeedEvent }) {
  const accent = event.event_type.toLowerCase().includes("battle") ? C.red : C.volt;
  return (
    <Card accent={accent}>
      <Eyebrow color={accent}>{event.event_type.replace(/_/g, " ").toUpperCase()}</Eyebrow>
      <Text style={s.headline}>{formatEventHeadline(event)}</Text>
      <Text style={s.meta}>{formatEventTime(event.generated_at)} · {event.user.tier}</Text>
    </Card>
  );
}

export default function FeedScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { items, cursor, lifecycleStage, loading, refreshing, loadingMore, error, refresh, loadMore, retry } = useFeed();

  useEffect(() => { track("feed_viewed"); }, []);

  const showEmpty = !loading && !error && items.length === 0 && lifecycleStage === "stage_a";

  const header = (
    <View style={s.header}>
      <Pressable onPress={() => router.back()} hitSlop={12}><Text style={s.back}>‹ Back</Text></Pressable>
      <Text style={s.title}>Feed</Text>
      <Text style={s.sub}>Progression from you and your friends — not endless scrolling.</Text>
    </View>
  );

  return (
    <View style={[s.screen, { paddingTop: insets.top + 10, paddingBottom: insets.bottom }]}> 
      {loading ? (
        <View style={s.content}>{header}<View style={s.centered}><ActivityIndicator color={C.volt} /><Text style={s.hint}>Loading feed…</Text></View></View>
      ) : error ? (
        <View style={s.content}>{header}<View style={s.centered}><Text style={s.error}>{error}</Text><Btn label="Retry" variant="ghost" onPress={() => void retry()} /></View></View>
      ) : showEmpty ? (
        <View style={s.content}>
          {header}
          <View style={s.centered}>
            <Card accent={C.volt}>
              <Eyebrow color={C.dim}>YOUR FEED</Eyebrow>
              <Text style={s.emptyTitle}>Your feed starts with progression.</Text>
              <Text style={s.hint}>Film a session first. Your progression and your friends' real skate activity show up here.</Text>
            </Card>
            <Text style={s.arrowHint}>↓ Start a session from Home or Flow</Text>
          </View>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.id}
          contentContainerStyle={s.listContent}
          ListHeaderComponent={header}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={C.volt} />}
          renderItem={({ item }) => <FeedEventCard event={item} />}
          onEndReached={() => { if (cursor) void loadMore(); }}
          onEndReachedThreshold={0.4}
          ListFooterComponent={loadingMore ? <ActivityIndicator color={C.volt} style={{ marginTop: 12 }} /> : null}
          ListEmptyComponent={<Text style={s.hint}>Your friends haven't posted progression yet — check back after your next session.</Text>}
        />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal },
  content: { flex: 1, paddingHorizontal: 20, gap: 14 },
  listContent: { paddingHorizontal: 20, paddingBottom: 28, gap: 12 },
  header: { paddingTop: 10, paddingBottom: 10 },
  back: { fontFamily: F.bold, fontSize: 14, color: C.volt },
  title: { fontFamily: F.heading, fontSize: 30, color: C.offwhite, marginTop: 14 },
  sub: { fontFamily: F.body, fontSize: 14, lineHeight: 20, color: C.dim, marginTop: 5 },
  headline: { fontFamily: F.bold, fontSize: 16, color: C.offwhite, marginTop: 4 },
  meta: { fontFamily: F.mono, fontSize: 10, color: C.dim, marginTop: 5 },
  centered: { flex: 1, justifyContent: "center", gap: 14 },
  hint: { fontFamily: F.body, fontSize: 13, color: C.dim, lineHeight: 19 },
  arrowHint: { fontFamily: F.body, fontSize: 12, color: C.dim, textAlign: "center" },
  emptyTitle: { fontFamily: F.bold, fontSize: 17, color: C.offwhite, marginTop: 4 },
  error: { fontFamily: F.body, fontSize: 13, color: C.red, textAlign: "center" },
});