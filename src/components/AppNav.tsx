import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { usePathname, useRouter } from "expo-router";
import { C, F } from "../theme";

type NavItem = { label: string; href: string; match: string[] };

const ITEMS: NavItem[] = [
  { label: "HOME", href: "/", match: ["/"] },
  { label: "FLOW", href: "/flow", match: ["/flow", "/trick", "/capture", "/analyzing", "/result"] },
  { label: "PTE.FLOW", href: "/pte", match: ["/pte"] },
  { label: "FEED", href: "/feed", match: ["/feed"] },
];

export function AppNav() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <View style={s.wrap} accessibilityRole="tablist">
      {ITEMS.map((item) => {
        const active = item.match.some((prefix) =>
          prefix === "/" ? pathname === "/" : pathname.startsWith(prefix),
        );
        return (
          <Pressable
            key={item.href}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            onPress={() => router.replace(item.href as never)}
            style={({ pressed }) => [s.item, pressed && { opacity: 0.7 }]}
          >
            <View style={[s.marker, active && s.markerActive]} />
            <Text style={[s.label, active && s.labelActive]}>{item.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    backgroundColor: C.charcoal,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: C.charcoal3,
    paddingTop: 8,
    paddingBottom: 4,
  },
  item: { flex: 1, minHeight: 44, alignItems: "center", justifyContent: "center", gap: 5 },
  marker: { width: 18, height: 2, borderRadius: 1, backgroundColor: "transparent" },
  markerActive: { backgroundColor: C.volt },
  label: { fontFamily: F.bold, fontSize: 9, letterSpacing: 0.8, color: C.dim },
  labelActive: { color: C.offwhite },
});
