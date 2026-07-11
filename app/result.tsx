import React, { useRef, useState } from "react";
import { View, Text, ScrollView, StyleSheet, Pressable, Alert } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { C, F } from "../src/theme";
import { Btn, Card, Eyebrow, Tag, LiteBanner, Field } from "../src/ui";
import { getFlowRedirect } from "../src/flow";
import { useSession } from "../src/session";
import { ManualOutcome } from "../src/types";

function OutcomeBtn({
  label,
  selected,
  onPress,
  color,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
  color: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[s.outcomeBtn, selected ? { borderColor: color, backgroundColor: C.charcoal3 } : null]}
    >
      <Text style={[s.outcomeBtnText, selected ? { color } : null]}>{label}</Text>
    </Pressable>
  );
}

export default function Result() {
  const router = useRouter();
  const { trick, analysis, setAnalysis, reportManualLog } = useSession();
  const insets = useSafeAreaInsets();
  const submitLock = useRef(false);
  const [submitting, setSubmitting] = useState(false);
  const [outcome, setOutcome] = useState<ManualOutcome | null>(null);
  const [attempts, setAttempts] = useState("1");
  const [spot, setSpot] = useState("");
  const [notes, setNotes] = useState("");

  const redirect = getFlowRedirect("result", { trick, analysis });
  if (redirect) return <Redirect href={redirect} />;

  const a = analysis!;
  const isSelfReport = a.selfReportOnly === true;
  const bannerMessage = isSelfReport
    ? "SELF-REPORT — no detection pipeline. Log what actually happened."
    : a.source === "sample"
      ? "SAMPLE SCRIPT — scripted analysis for illustration, not your footage."
      : undefined;

  const evidenceColor =
    a.evidenceClass === "DETECTED" ? C.volt : a.evidenceClass === "ESTIMATE" ? C.amber : C.red;

  const handleSave = async () => {
    if (!outcome || submitLock.current) return;

    submitLock.current = true;
    setSubmitting(true);
    try {
      await reportManualLog({
        manualOutcome: outcome,
        attempts: Math.min(999, Math.max(1, parseInt(attempts, 10) || 1)),
        spot: spot.trim(),
        notes: notes.trim(),
      });
      router.replace("/log");
    } catch (error) {
      const message = error instanceof Error ? error.message : "The attempt could not be logged.";
      Alert.alert("Couldn't save the attempt", message);
    } finally {
      submitLock.current = false;
      setSubmitting(false);
    }
  };

  const handleAnotherClip = () => {
    setAnalysis(null);
    router.back();
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: C.charcoal }}
      contentContainerStyle={[
        s.content,
        { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 24 },
      ]}
      keyboardShouldPersistTaps="handled"
    >
      <LiteBanner message={bannerMessage} />

      <View style={{ gap: 2 }}>
        <Eyebrow>
          CALLED: <Text style={{ color: a.mismatch ? C.red : C.volt }}>{a.trickCalled.toUpperCase()}</Text>
          {a.trickOnFilm && a.mismatch ? `  ·  ON FILM: ${a.trickOnFilm.toUpperCase()}` : ""}
        </Eyebrow>
        <Text style={s.title}>{a.trickOnFilm ?? a.trickCalled}</Text>
        <Text style={s.engineStamp}>{a.engineVersion}</Text>
      </View>

      <Card accent={a.abstained ? C.red : isSelfReport ? C.amber : C.volt}>
        <View style={s.metaRow}>
          <Tag kind={a.evidenceClass} />
          <Text style={[s.confidence, { color: evidenceColor }]}>{a.confidence}% confidence</Text>
        </View>
        <View style={s.ratingRow}>
          {a.abstained ? (
            <Text style={s.noRating}>NO RATING</Text>
          ) : a.rating !== null ? (
            <View style={{ flexDirection: "row", alignItems: "baseline", gap: 8 }}>
              <Text style={s.rating}>{a.rating.toFixed(1)}</Text>
              <Text style={s.outOf}>/ 10</Text>
            </View>
          ) : (
            <Text style={s.selfReport}>MANUAL LOG</Text>
          )}
          <Text style={s.verdict}>{a.verdict}</Text>
        </View>
        {a.abstainReason ? (
          <Text style={s.abstainReason}>Abstain: {a.abstainReason}</Text>
        ) : null}
      </Card>

      <Card>
        <Eyebrow color={C.volt}>RECEIPTS</Eyebrow>
        {a.receipts.map((receipt) => (
          <View key={receipt.id} style={s.receiptRow}>
            <Text style={s.receiptLabel}>{receipt.label.toUpperCase()}</Text>
            <Text style={s.receiptDetail}>{receipt.detail}</Text>
          </View>
        ))}
      </Card>

      <View style={{ gap: 10 }}>
        <Eyebrow>OBSERVATIONS</Eyebrow>
        {a.observations.map((observation, index) => (
          <View key={index} style={s.obsRow}>
            <Text style={s.obsText}>{observation.text}</Text>
            <Tag kind={observation.tag} />
          </View>
        ))}
      </View>

      <Card accent={C.volt}>
        <Eyebrow color={C.volt}>LOG THIS ATTEMPT</Eyebrow>
        <Text style={s.body}>
          {a.abstained
            ? "The engine abstained, but your self-report can still preserve what happened."
            : "What happened? This is your record — not a guess from the engine."}
        </Text>

        <View style={s.outcomeRow}>
          <OutcomeBtn
            label="Landed"
            selected={outcome === "landed"}
            onPress={() => setOutcome("landed")}
            color={C.volt}
          />
          <OutcomeBtn
            label="Missed"
            selected={outcome === "missed"}
            onPress={() => setOutcome("missed")}
            color={C.red}
          />
          <OutcomeBtn
            label="Unsure"
            selected={outcome === "unsure"}
            onPress={() => setOutcome("unsure")}
            color={C.amber}
          />
        </View>

        <Field
          label="ATTEMPTS"
          value={attempts}
          onChangeText={setAttempts}
          keyboardType="number-pad"
          placeholder="1"
        />
        <Field label="SPOT" value={spot} onChangeText={setSpot} placeholder="Where did you skate?" />
        <Field
          label="NOTES"
          value={notes}
          onChangeText={setNotes}
          placeholder="Anything worth remembering"
          multiline
          numberOfLines={3}
          style={{ minHeight: 72, textAlignVertical: "top" }}
        />

        <Btn label="Save to log" onPress={() => void handleSave()} disabled={!outcome || submitting} />
      </Card>

      <Card accent={C.red}>
        <Eyebrow color={C.red}>WORK ON</Eyebrow>
        <Text style={s.body}>{a.workOn}</Text>
      </Card>

      {a.styleNote ? <Text style={s.styleNote}>Style: {a.styleNote}</Text> : null}

      <View style={{ gap: 10, marginTop: 8 }}>
        {a.abstained ? <Btn label="Refilm the clip" onPress={handleAnotherClip} /> : null}
        <Btn label="Another clip" variant="ghost" onPress={handleAnotherClip} />
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  content: { paddingHorizontal: 24, gap: 16 },
  title: { fontFamily: F.heading, fontSize: 26, color: C.offwhite },
  engineStamp: { fontFamily: F.mono, fontSize: 9, color: C.dim, letterSpacing: 0.6 },
  metaRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  confidence: { fontFamily: F.mono, fontSize: 11 },
  ratingRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  rating: { fontFamily: F.heading, fontSize: 46, color: C.volt, lineHeight: 48 },
  outOf: { fontFamily: F.mono, fontSize: 12, color: C.dim },
  noRating: { fontFamily: F.heading, fontSize: 22, color: C.red },
  selfReport: { fontFamily: F.heading, fontSize: 18, color: C.amber },
  verdict: { fontFamily: F.body, fontSize: 13, color: C.offwhite, flex: 1, textAlign: "right" },
  abstainReason: { fontFamily: F.mono, fontSize: 10, color: C.red, lineHeight: 15, marginTop: 4 },
  receiptRow: { gap: 2, paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: C.charcoal3 },
  receiptLabel: { fontFamily: F.mono, fontSize: 9, color: C.dim, letterSpacing: 0.6 },
  receiptDetail: { fontFamily: F.body, fontSize: 13, lineHeight: 18, color: C.offwhite },
  obsRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: 10 },
  obsText: { fontFamily: F.body, fontSize: 14, lineHeight: 20, color: C.offwhite, flex: 1 },
  body: { fontFamily: F.body, fontSize: 14, lineHeight: 21, color: C.offwhite },
  styleNote: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
  outcomeRow: { flexDirection: "row", gap: 8 },
  outcomeBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: C.aluminum,
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: "center",
  },
  outcomeBtnText: { fontFamily: F.bold, fontSize: 13, color: C.dim },
});
