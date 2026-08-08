import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { usePathname, useRouter } from "expo-router";
import { C, F, SPACE } from "../theme";

type NavItem = { label: string; href: string };

/** Skate product tabs: Home / Flow / PTE. Feed lives under Home. */
const ITEMS: NavItem[] = [
  { label: "HOME", href: "/" },
  { label: "FLOW", href: "/flow" },
  { label: "PTE.FLOW", href: "/pte" },
];

function isSelected(pathname: string, href: string): boolean {
  if (href === "/") {
    return (
      pathname === "/" ||
      pathname.startsWith("/feed") ||
      pathname.startsWith("/notifications") ||
      pathname.startsWith("/settings") ||
      pathname.startsWith("/history")
    );
  }
  if (href === "/flow") {
    return (
      pathname.startsWith("/flow") ||
      pathname.startsWith("/trick") ||
      pathname.startsWith("/capture") ||
      pathname.startsWith("/analyzing") ||
      pathname.startsWith("/result") ||
      pathname.startsWith("/recap")
    );
  }
  return pathname.startsWith(href);
}

export function AppNav() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <View style={s.wrap} accessibilityRole="tablist">
      {ITEMS.map((item) => {
        const selected = isSelected(pathname, item.href);
        return (
          <Pressable
            key={item.href}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            onPress={() => router.replace(item.href as never)}
            style={({ pressed }) => [s.item, pressed && { opacity: 0.7 }]}
          >
            <View style={[s.marker, selected && s.markerActive]} />
            <Text style={[s.label, selected && s.labelActive]}>{item.label}</Text>
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
    borderTopColor: C.charcoal5,
    paddingTop: SPACE.sm,
    paddingBottom: 4,
  },
  item: { flex: 1, minHeight: 44, alignItems: "center", justifyContent: "center", gap: 5 },
  marker: { width: 22, height: 2, borderRadius: 0, backgroundColor: "transparent" },
  markerActive: { backgroundColor: C.volt },
  label: { fontFamily: F.bold, fontSize: 9, letterSpacing: 1, color: C.dim },
  labelActive: { color: C.offwhite },
});
