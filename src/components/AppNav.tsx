import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { usePathname, useRouter } from "expo-router";
import { C, F } from "../theme";

type NavItem = { label: string; href: string; match: string[] };

const ITEMS: NavItem[] = [
  { label: "HOME", href: "/", match: ["/"] },
  { label: "FLOW", href: "/flow", match: ["/flow", "/trick", "/capture", "/analyzing", "/result", "/recap"] },
  { label: "PTE", href: "/pte", match: ["/pte", "/history"] },
];

export function AppNav() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <View style={s.wrap} accessibilityRole="tablist">
      {ITEMS.map((item) => {
        const active = item.match.some((prefix) => prefix === "/" ? pathname === "/" : pathname.startsWith(prefix));
        return (
          <Pressable
            key={item.href}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            onPress={() => router.replace(item.href as never)}
            style={({ pressed }) => [s.item, pressed && { opacity: 0.7 }]}
          >
            <View style={[s.dot, active && s.dotActive]} />
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
    paddingTop: 7,
    paddingBottom: 4,
  },
  item: { flex: 1, minHeight: 46, alignItems: "center", justifyContent: "center", gap: 5 },
  dot: { width: 4, height: 4, borderRadius: 2, backgroundColor: "transparent" },
  dotActive: { backgroundColor: C.volt },
  label: { fontFamily: F.bold, fontSize: 10, letterSpacing: 1.2, color: C.dim },
  labelActive: { color: C.volt },
});