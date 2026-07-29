import React, { useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect, useLocalSearchParams, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { track } from "../src/analytics";
import { updateSkateSession } from "../src/api/sessionApi";
import { useSkateSession } from "../src/skateSession/skateSessionContext";
import { useSession } from "../src/session";
import { C, F } from "../src/theme";
import { Btn, Eyebrow, Field } from "../src/ui";
import { filterTrickLibraryByQuery } from "../src/tricks/trickSearch";
import { canonicalTrickName } from "../src/tricks/trickFormat";
import { DIRECTION_MODIFIERS, POPULAR_TRICKS, STANCE_MODIFIERS, type TrickModifier } from "../src/tricks/trickLibrary";
import { buildSelectedTrick } from "../src/tricks/types";

function toggleModifier(current: TrickModifier[], mod: TrickModifier): TrickModifier[] {
  const group = STANCE_MODIFIERS.includes(mod) ? STANCE_MODIFIERS : DIRECTION_MODIFIERS;
  const withoutGroup = current.filter((m) => !group.includes(m));
  if (current.includes(mod)) return withoutGroup;
  return [...withoutGroup, mod];
}

export default function TrickPicker() {
  const router = useRouter();
  const params = useLocalSearchParams<{ returnTo?: string }>();
  const returnTo = typeof params.returnTo === "string" && params.returnTo.startsWith("/") ? params.returnTo : "/flow";
  const { setSelectedTrick } = useSession();
  const { activeSession, hasActiveSession, hydrateState, refreshActiveSession } = useSkateSession();
  const insets = useSafeAreaInsets();
  const [query, setQuery] = useState("");
  const [baseTrick, setBaseTrick] = useState<string | null>(null);
  const [modifiers, setModifiers] = useState<TrickModifier[]>([]);
  const [saving, setSaving] = useState(false);

  const categories = useMemo(() => filterTrickLibraryByQuery(query), [query]);
  const canonicalPreview = baseTrick ? canonicalTrickName(baseTrick, modifiers) : "";

  if (hydrateState === "loading") {
    return <View style={[s.screen, s.centered, { paddingTop: insets.top + 16 }]}><ActivityIndicator color={C.volt} /></View>;
  }
  if (!hasActiveSession) return <Redirect href="/flow" />;

  async function confirmSelection() {
    if (!baseTrick || !canonicalPreview || saving) return;
    setSaving(true);
    try {
      const selected = buildSelectedTrick(baseTrick, modifiers, canonicalPreview);
      setSelectedTrick(selected);
      if (activeSession?.id) {
        const updated = await updateSkateSession(activeSession.id, { focus_trick: selected.canonicalName });
        if (updated.ok) await refreshActiveSession();
      }
      track("trick_selected", { trick: selected.canonicalName, trick_id: selected.trickId });
      router.replace(returnTo as never);
    } finally {
      setSaving(false);
    }
  }

  return (
    <View style={[s.screen, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <View style={{ gap: 6 }}>
        <Eyebrow color={C.volt}>CALL THE TRICK</Eyebrow>
        <Text style={s.title}>What are you trying?</Text>
        <Text style={s.sub}>Pick the base trick first. Add stance or direction only when it matters.</Text>
      </View>

      <Field label="Search" value={query} onChangeText={setQuery} placeholder="Kickflip, 50-50…" autoCapitalize="none" autoCorrect={false} />

      {!query.trim() ? (
        <View style={{ gap: 8 }}>
          <Eyebrow color={C.volt}>POPULAR</Eyebrow>
          <View style={s.chipRow}>{POPULAR_TRICKS.map((t) => <Pressable key={t} onPress={() => setBaseTrick(t)} style={[s.chip, baseTrick === t && s.chipActive]}><Text style={[s.chipText, baseTrick === t && s.chipTextActive]}>{t}</Text></Pressable>)}</View>
        </View>
      ) : null}

      <View style={{ gap: 8 }}>
        <Eyebrow>STANCE</Eyebrow>
        <View style={s.chipRow}>{STANCE_MODIFIERS.map((m) => <Pressable key={m} onPress={() => setModifiers((prev) => toggleModifier(prev, m))} style={[s.chip, modifiers.includes(m) && s.chipActive]}><Text style={[s.chipText, modifiers.includes(m) && s.chipTextActive]}>{m}</Text></Pressable>)}</View>
      </View>

      <View style={{ gap: 8 }}>
        <Eyebrow>DIRECTION</Eyebrow>
        <View style={s.chipRow}>{DIRECTION_MODIFIERS.map((m) => <Pressable key={m} onPress={() => setModifiers((prev) => toggleModifier(prev, m))} style={[s.chip, modifiers.includes(m) && s.chipActive]}><Text style={[s.chipText, modifiers.includes(m) && s.chipTextActive]}>{m}</Text></Pressable>)}</View>
      </View>

      {canonicalPreview ? <View style={s.preview}><Eyebrow color={C.volt}>LOCKED IN</Eyebrow><Text style={s.previewText}>{canonicalPreview}</Text></View> : null}

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ gap: 14, paddingBottom: 12 }}>
        {categories.map((cat) => <View key={cat.id} style={{ gap: 8 }}><Eyebrow>{cat.label.toUpperCase()}</Eyebrow><View style={s.chipRow}>{cat.tricks.map((t) => <Pressable key={`${cat.id}-${t}`} onPress={() => setBaseTrick(t)} style={[s.chip, baseTrick === t && s.chipActive]}><Text style={[s.chipText, baseTrick === t && s.chipTextActive]}>{t}</Text></Pressable>)}</View></View>)}
        {query.trim() && categories.length === 0 ? <Text style={s.sub}>No tricks match that search.</Text> : null}
      </ScrollView>

      <View style={{ gap: 10 }}><Btn label={saving ? "Saving…" : "Confirm trick"} onPress={() => void confirmSelection()} disabled={!baseTrick || saving} /><Btn label="Back" variant="ghost" onPress={() => router.back()} /></View>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.charcoal, paddingHorizontal: 24, gap: 12 },
  centered: { alignItems: "center", justifyContent: "center" },
  title: { fontFamily: F.heading, fontSize: 28, lineHeight: 32, color: C.offwhite },
  sub: { fontFamily: F.body, fontSize: 13, lineHeight: 19, color: C.dim },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { borderWidth: StyleSheet.hairlineWidth, borderColor: C.charcoal3, borderRadius: 10, paddingHorizontal: 11, paddingVertical: 9, backgroundColor: C.charcoal2 },
  chipActive: { borderColor: C.volt, backgroundColor: C.charcoal3 },
  chipText: { fontFamily: F.body, fontSize: 13, color: C.offwhite },
  chipTextActive: { color: C.volt, fontFamily: F.bold },
  preview: { borderLeftWidth: 4, borderLeftColor: C.volt, paddingLeft: 12, gap: 4 },
  previewText: { fontFamily: F.heading, fontSize: 20, color: C.offwhite },
});
