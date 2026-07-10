import React from "react";
import { View, Text, ScrollView, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow, Tag, LiteBanner } from "../src/ui";
import { useSession } from "../src/session";

export default function Result() {
  const router = useRouter();
  const { analysis, logClip } = useSession();
  const insets = useSafeAreaInsets();

  if (!analysis) {
    router.replace("/");
    return null;
  }

  const a = analysis;

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: C.charcoal }}
      contentContainerStyle={[
        s.content,
        { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 24 },
      ]}
    >
      <LiteBanner />

      <View style={{ gap: 2 }}>
        <Eyebrow>
          CALLED: <Text style={{ color: a.mismatch ? C.red : C.volt }}>{a.trickCalled.toUpperCase()}</Text>
          {a.trickOnFilm && a.mismatch ? `  ·  ON FILM: ${a.trickOnFilm.toUpperCase()}` : ""}
        </Eyebrow>
        <Text style={s.title}>{a.trickOnFilm ?? a.trickCalled}</Text>
      </View>

      <Card accent={a.abstained ? C.red : C.volt}>
        <View style={s.ratingRow}>
          {a.abstained ? (
            <Text style={s.noRating}>NO RATING</Text>
          ) : (
            <View style={{ flexDirection: "row", alignItems: "baseline", gap: 8 }}>
              <Text style={s.rating}>{a.rating!.toFixed(1)}</Text>
              <Text style={s.outOf}>/ 10</Text>
            </View>
          )}
          <Text style={s.verdict}>{a.verdict}</Text>
        </View>
      </Card>

      <View style={{ gap: 10 }}>
        {a.observations.map((o, i) => (
          <View key={i} style={s.obsRow}>
            <Text style={s.obsText}>{o.text}</Text>
            <Tag kind={o.tag} />
          </View>
        ))}
      </View>

      <Card accent={C.red}>
        <Eyebrow color={C.red}>WORK ON</Eyebrow>
        <Text style={s.body}>{a.workOn}</Text>
      </Card>

      {a.styleNote ? <Text style={s.styleNote}>Style: {a.styleNote}</Text> : null}

      <View style={{ gap: 10, marginTop: 8 }}>
        {a.abstained ? (
          <Btn label="Refilm the clip" onPress={() => router.replace("/capture")} />
        ) : (
          <Btn
            label="Log it"
            onPress={() => {
              logClip(a);
              router.replace("/log");
            }}
          />
        )}
        <Btn label="Another clip" variant="ghost" onPress={() => router.replace("/capture")} />
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  content: { paddingHorizontal: 24, gap: 16 },
  title: { fontFamily: F.heading, fontSize: 26, color: C.offwhite },
  ratingRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  rating: { fontFamily: F.heading, fontSize: 46, color: C.volt, lineHeight: 48 },
  outOf: { fontFamily: F.mono, fontSize: 12, color: C.dim },
  noRating: { fontFamily: F.heading, fontSize: 22, color: C.red },
  verdict: { fontFamily: F.body, fontSize: 13, color: C.offwhite, flex: 1, textAlign: "right" },
  obsRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: 10 },
  obsText: { fontFamily: F.body, fontSize: 14, lineHeight: 20, color: C.offwhite, flex: 1 },
  body: { fontFamily: F.body, fontSize: 14, lineHeight: 21, color: C.offwhite },
  styleNote: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
});
