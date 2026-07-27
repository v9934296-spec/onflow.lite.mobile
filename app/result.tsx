import React, { useRef, useState } from "react";
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { getFlowRedirect } from "../src/flow";
import { useSession } from "../src/session";
import { C, F } from "../src/theme";
import type { ManualOutcome } from "../src/types";
import { Btn, Card, Eyebrow, Field, LiteBanner, Tag } from "../src/ui";

function OutcomeBtn({
  label,
  selected,
  onPress,
  color,
  disabled,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
  color: string;
  disabled?: boolean;
}) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={[
        s.outcomeBtn,
        selected ? { borderColor: color, backgroundColor: C.charcoal3 } : null,
        disabled ? { opacity: 0.5 } : null,
      ]}
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

  const currentAnalysis = analysis!;
  const isSelfReport = currentAnalysis.selfReportOnly === true;
  const bannerMessage = isSelfReport
    ? "SELF-REPORT — no detection pipeline. Log what actually happened."
    : currentAnalysis.source === "sample"
      ? "SAMPLE SCRIPT — scripted analysis for illustration, not your footage."
      : undefined;

  const evidenceColor =
    currentAnalysis.evidenceClass === "DETECTED"
      ? C.volt
      : currentAnalysis.evidenceClass === "ESTIMATE"
        ? C.amber
        : C.red;

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
      Alert.alert(
        "Couldn't save the attempt",
        error instanceof Error ? error.message : "The attempt could not be logged.",
      );
    } finally {
      submitLock.current = false;
      setSubmitting(false);
    }
  };

  const handleAnotherClip = () => {
    setAnalysis(null);
    router.replace("/capture");
  };

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: C.charcoal }}
      contentContainerStyle={[
        s.content,
        { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 24 },
      ]}
    >
      <LiteBanner message={bannerMessage} />

      <View style={{ gap: 2 }}>
        <Eyebrow>
          CALLED:{" "}
          <Text style={{ color: currentAnalysis.mismatch ? C.red : C.volt }}>
            {currentAnalysis.trickCalled.toUpperCase()}
          </Text>
          {currentAnalysis.trickOnFilm && currentAnalysis.mismatch
            ? `  ·  ON FILM: ${currentAnalysis.trickOnFilm.toUpperCase()}`
            : ""}
        </Eyebrow>
        <Text style={s.title}>{currentAnalysis.trickOnFilm ?? currentAnalysis.trickCalled}</Text>
        <Text style={s.engineStamp}>{currentAnalysis.engineVersion}</Text>
      </View>

      <Card accent={currentAnalysis.abstained ? C.red : isSelfReport ? C.amber : C.volt}>
        <View style={s.metaRow}>
          <Tag kind={currentAnalysis.evidenceClass} />
          <Text style={[s.confidence, { color: currentAnalysis.confidence == null ? C.dim : evidenceColor }]}>
            {currentAnalysis.confidence == null
              ? "CONFIDENCE NOT PROVIDED"
              : `${Math.round(currentAnalysis.confidence)}% confidence`}
          </Text>
        </View>
        <View style={s.ratingRow}>
          {currentAnalysis.abstained ? (
            <Text style={s.noRating}>NO RATING</Text>
          ) : currentAnalysis.rating !== null ? (
            <View style={{ flexDirection: "row", alignItems: "baseline", gap: 8 }}>
              <Text style={s.rating}>{currentAnalysis.rating.toFixed(1)}</Text>
              <Text style={s.outOf}>/ 10</Text>
            </View>
          ) : (
            <Text style={s.selfReport}>MANUAL LOG</Text>
          )}
          <Text style={s.verdict}>{currentAnalysis.verdict}</Text>
        </View>
        {currentAnalysis.abstainReason ? (
          <Text style={s.abstainReason}>Abstain: {currentAnalysis.abstainReason}</Text>
        ) : null}
      </Card>

      <Card>
        <Eyebrow color={C.volt}>RECEIPTS</Eyebrow>
        {currentAnalysis.receipts.map((receipt) => (
          <View key={receipt.id} style={s.receiptRow}>
            <Text style={s.receiptLabel}>{receipt.label.toUpperCase()}</Text>
            <Text style={s.receiptDetail}>{receipt.detail}</Text>
          </View>
        ))}
      </Card>

      <View style={{ gap: 10 }}>
        <Eyebrow>OBSERVATIONS</Eyebrow>
        {currentAnalysis.observations.map((observation, index) => (
          <View key={`${observation.tag}-${index}`} style={s.obsRow}>
            <Text style={s.obsText}>{observation.text}</Text>
            <Tag kind={observation.tag} />
          </View>
        ))}
      </View>

      <Card accent={C.volt}>
        <Eyebrow color={C.volt}>LOG THIS ATTEMPT</Eyebrow>
        <Text style={s.body}>What happened? This is your record — not a guess from the engine.</Text>

        <View style={s.outcomeRow}>
          <OutcomeBtn
            label="Landed"
            selected={outcome === "landed"}
            onPress={() => setOutcome("landed")}
            color={C.volt}
            disabled={submitting}
          />
          <OutcomeBtn
            label="Missed"
            selected={outcome === "missed"}
            onPress={() => setOutcome("missed")}
            color={C.red}
            disabled={submitting}
          />
          <OutcomeBtn
            label="Unsure"
            selected={outcome === "unsure"}
            onPress={() => setOutcome("unsure")}
            color={C.amber}
            disabled={submitting}
          />
        </View>

        <Field
          label="ATTEMPTS"
          value={attempts}
          onChangeText={setAttempts}
          keyboardType="number-pad"
          placeholder="1"
        />
        <Field
          label="SPOT"
          value={spot}
          onChangeText={setSpot}
          placeholder="Where did you skate?"
        />
        <Field
          label="NOTES"
          value={notes}
          onChangeText={setNotes}
          placeholder="Anything worth remembering"
          multiline
          numberOfLines={3}
          style={{ minHeight: 72, textAlignVertical: "top" }}
        />

        <Btn
          label={submitting ? "Saving…" : "Save to log"}
          onPress={() => void handleSave()}
          disabled={!outcome || submitting}
        />
      </Card>

      <Card accent={C.red}>
        <Eyebrow color={C.red}>WORK ON</Eyebrow>
        <Text style={s.body}>{currentAnalysis.workOn}</Text>
      </Card>

      {currentAnalysis.styleNote ? <Text style={s.styleNote}>Style: {currentAnalysis.styleNote}</Text> : null}

      <View style={{ gap: 10, marginTop: 8 }}>
        {currentAnalysis.abstained ? (
          <Btn label="Refilm the clip" onPress={handleAnotherClip} disabled={submitting} />
        ) : null}
        <Btn
          label="Another clip"
          variant="ghost"
          onPress={handleAnotherClip}
          disabled={submitting}
        />
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
    borderColor: C.charcoal4,
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: "center",
  },
  outcomeBtnText: { fontFamily: F.bold, fontSize: 13, color: C.dim },
});
