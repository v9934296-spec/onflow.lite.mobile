import React from "react";
import { View, Text, ScrollView, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow } from "../src/ui";
import { RatingLine, BreakdownBars } from "../src/charts";
import { useSession } from "../src/session";

export default function Log() {
  const router = useRouter();
  const { log, resetLoop } = useSession();
  const insets = useSafeAreaInsets();

  const rated = log.filter((e) => e.analysis.rating !== null);
  const ratings = rated.map((e) => e.analysis.rating as number);
  const latest = rated.length > 0 ? rated[rated.length - 1] : null;

  const allObs = log.flatMap((e) => e.analysis.observations);
  const detected = allObs.filter((o) => o.tag === "DETECTED").length;
  const estimated = allObs.filter((o) => o.tag === "ESTIMATE").length;
  const noEvidence = allObs.filter((o) => o.tag === "NO EVIDENCE").length;

  const dateLabel = new Date()
    .toLocaleDateString("en-US", { month: "short", day: "numeric" })
    .toUpperCase();

  return (
    <View style={{ flex: 1, backgroundColor: C.charcoal }}>
      <ScrollView contentContainerStyle={[s.content, { paddingTop: insets.top + 16 }]}>
        <Eyebrow>SESSION LOG · {dateLabel}</Eyebrow>

        {log.length === 0 ? (
          <View style={s.empty}>
            <Text style={s.emptyTitle}>Nothing logged yet.</Text>
            <Text style={s.emptySub}>
              Film a clip and the log builds itself. No forms, no manual entry.
            </Text>
          </View>
        ) : (
          <>
            {ratings.length > 0 && (
              <Card>
                <Eyebrow color={C.volt}>P.T.E. · RATING OVER SESSION</Eyebrow>
                <RatingLine ratings={ratings} />
              </Card>
            )}

            {latest?.analysis.breakdown && (
              <Card>
                <Eyebrow color={C.volt}>
                  LAST CLIP ·{" "}
                  {(latest.analysis.trickOnFilm ?? latest.analysis.trickCalled).toUpperCase()}{" "}
                  BREAKDOWN
                </Eyebrow>
                <BreakdownBars items={latest.analysis.breakdown} />
              </Card>
            )}

            <Text style={s.evidence}>
              EVIDENCE THIS SESSION: <Text style={{ color: C.volt }}>{detected} detected</Text>
              {" · "}
              <Text style={{ color: C.amber }}>{estimated} estimated</Text>
              {noEvidence > 0 ? (
                <>
                  {" · "}
                  <Text style={{ color: C.red }}>{noEvidence} no evidence</Text>
                </>
              ) : null}
            </Text>

            {log.map((e, i) => (
              <View key={e.id} style={s.logCard}>
                {e.analysis.rating !== null ? (
                  <Text style={s.logRating}>{e.analysis.rating.toFixed(1)}</Text>
                ) : (
                  <Text style={[s.logRating, { color: C.dim, fontSize: 14 }]}>N/R</Text>
                )}
                <View style={{ flex: 1, gap: 2 }}>
                  <Text style={s.logTrick}>{e.analysis.trickOnFilm ?? e.analysis.trickCalled}</Text>
                  <Text style={s.logMeta}>
                    clip {i + 1} · {e.analysis.source === "sample" ? "sample" : "your footage"}
                    {e.analysis.mismatch ? " · called wrong" : ""}
                  </Text>
                </View>
              </View>
            ))}
          </>
        )}
      </ScrollView>

      <View style={[s.footer, { paddingBottom: insets.bottom + 16 }]}>
        <Btn
          label="Film a clip"
          onPress={() => {
            resetLoop();
            router.push("/trick");
          }}
        />
        <Btn label="Home" variant="ghost" onPress={() => router.replace("/")} />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  content: { paddingHorizontal: 24, gap: 14, paddingBottom: 16 },
  empty: { paddingVertical: 60, gap: 10 },
  emptyTitle: { fontFamily: F.heading, fontSize: 24, color: C.offwhite },
  emptySub: { fontFamily: F.body, fontSize: 14, lineHeight: 20, color: C.dim },
  evidence: { fontFamily: F.mono, fontSize: 10, color: C.dim, letterSpacing: 0.5 },
  logCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: C.charcoal2,
    borderWidth: 1,
    borderColor: C.aluminum,
    borderRadius: 10,
    padding: 14,
  },
  logRating: { fontFamily: F.heading, fontSize: 20, color: C.volt, minWidth: 44 },
  logTrick: { fontFamily: F.bold, fontSize: 14, color: C.offwhite },
  logMeta: { fontFamily: F.mono, fontSize: 10, color: C.dim },
  footer: { paddingHorizontal: 24, paddingTop: 10, gap: 10, backgroundColor: C.charcoal },
});
